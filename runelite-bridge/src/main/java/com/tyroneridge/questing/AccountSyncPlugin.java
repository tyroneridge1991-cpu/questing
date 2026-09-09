package com.tyroneridge.questing;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.inject.Provides;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.inject.Inject;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.Client;
import net.runelite.api.GameState;
import net.runelite.api.InventoryID;
import net.runelite.api.Item;
import net.runelite.api.ItemContainer;
import net.runelite.api.Player;
import net.runelite.api.Skill;
import net.runelite.api.Quest;
import net.runelite.api.QuestState;
import net.runelite.api.coords.WorldPoint;
import net.runelite.api.events.GameStateChanged;
import net.runelite.api.events.GameTick;
import net.runelite.api.events.ItemContainerChanged;
import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;
import net.runelite.client.eventbus.Subscribe;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;

@Slf4j
@PluginDescriptor(
        name = "Quest Navigator Account Sync",
        description = "Publishes local RuneLite account state to OSRS Quest Navigator. Read-only; never controls the game.",
        tags = {"quest", "ironman", "skills", "bank", "inventory", "equipment", "sync"}
)
public class AccountSyncPlugin extends Plugin
{
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();
    private static final Path DIR = Path.of(System.getProperty("user.home"), "AppData", "Local", "OSRSQuestNavigator");
    private static final Path FILE = DIR.resolve("account.json");
    private static final Path TEMP = DIR.resolve("account.json.tmp");

    @Inject private Client client;
    @Inject private AccountSyncConfig config;

    @Override
    protected void startUp()
    {
        writeSnapshot();
        log.info("Quest Navigator account sync started; local file: {}", FILE);
    }

    @Override
    protected void shutDown()
    {
        // Leave the last snapshot in place so the external app can show the last known state.
    }

    @Subscribe
    public void onGameTick(GameTick event)
    {
        if (config.syncEnabled())
        {
            writeSnapshot();
        }
    }

    @Subscribe
    public void onGameStateChanged(GameStateChanged event)
    {
        if (config.syncEnabled() && event.getGameState() == GameState.LOGGED_IN)
        {
            writeSnapshot();
        }
    }

    @Subscribe
    public void onItemContainerChanged(ItemContainerChanged event)
    {
        if (config.syncEnabled())
        {
            InventoryID id = event.getContainer().getId();
            if (id == InventoryID.INVENTORY || id == InventoryID.EQUIPMENT || id == InventoryID.BANK)
            {
                writeSnapshot();
            }
        }
    }

    private void writeSnapshot()
    {
        if (client.getGameState() != GameState.LOGGED_IN)
        {
            return;
        }

        try
        {
            Files.createDirectories(DIR);
            Map<String, Object> root = new LinkedHashMap<>();
            root.put("schema", 1);
            root.put("timestamp", System.currentTimeMillis());
            root.put("username", client.getLocalPlayer() == null ? "" : safe(client.getLocalPlayer().getName()));

            Player player = client.getLocalPlayer();
            if (player != null)
            {
                WorldPoint p = player.getWorldLocation();
                if (p != null)
                {
                    Map<String, Object> location = new LinkedHashMap<>();
                    location.put("x", p.getX());
                    location.put("y", p.getY());
                    location.put("plane", p.getPlane());
                    root.put("location", location);
                }
            }

            Map<String, Object> skills = new LinkedHashMap<>();
            for (Skill skill : Skill.values())
            {
                String name = skill.getName().toLowerCase();
                Map<String, Object> value = new LinkedHashMap<>();
                value.put("level", client.getRealSkillLevel(skill));
                value.put("boosted", client.getBoostedSkillLevel(skill));
                value.put("xp", client.getSkillExperience(skill));
                skills.put(name, value);
            }
            root.put("skills", skills);

            Map<String, String> quests = new LinkedHashMap<>();
            for (Quest quest : Quest.values())
            {
                QuestState state = quest.getState(client);
                quests.put(quest.getName(), state == null ? "UNKNOWN" : state.name());
            }
            root.put("quests", quests);

            root.put("inventory", items(InventoryID.INVENTORY));
            root.put("equipment", items(InventoryID.EQUIPMENT));
            root.put("bank", items(InventoryID.BANK));
            root.put("bankVisible", client.getItemContainer(InventoryID.BANK) != null);

            // Useful account/client state for planning. No credentials, tokens, or chat are exported.
            Map<String, Object> account = new LinkedHashMap<>();
            account.put("combatLevel", player == null ? 0 : player.getCombatLevel());
            account.put("runEnergy", client.getEnergy());
            account.put("runEnabled", client.isStretchedEnabled());
            root.put("account", account);

            String json = GSON.toJson(root);
            Files.writeString(TEMP, json, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE);
            try
            {
                Files.move(TEMP, FILE, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            }
            catch (AtomicMoveNotSupportedException e)
            {
                Files.move(TEMP, FILE, StandardCopyOption.REPLACE_EXISTING);
            }
        }
        catch (IOException | RuntimeException e)
        {
            log.debug("Unable to publish account snapshot", e);
        }
    }

    private Map<String, Object> items(InventoryID id)
    {
        Map<String, Object> out = new LinkedHashMap<>();
        ItemContainer container = client.getItemContainer(id);
        if (container == null)
        {
            return out;
        }
        for (int slot = 0; slot < container.size(); slot++)
        {
            Item item = container.getItem(slot);
            if (item == null || item.getId() <= 0 || item.getQuantity() <= 0)
            {
                continue;
            }
            Map<String, Object> value = new LinkedHashMap<>();
            value.put("id", item.getId());
            value.put("quantity", item.getQuantity());
            value.put("slot", slot);
            out.put(Integer.toString(slot), value);
        }
        return out;
    }

    private static String safe(String value)
    {
        return value == null ? "" : value;
    }

    @Provides
    AccountSyncConfig provideConfig(net.runelite.client.config.ConfigManager configManager)
    {
        return configManager.getConfig(AccountSyncConfig.class);
    }

    @ConfigGroup("questnavigatoraccountsync")
    public interface AccountSyncConfig extends Config
    {
        @ConfigItem(keyName = "syncEnabled", name = "Enable account sync", description = "Write read-only account state to the local Quest Navigator file")
        default boolean syncEnabled()
        {
            return true;
        }
    }
}
