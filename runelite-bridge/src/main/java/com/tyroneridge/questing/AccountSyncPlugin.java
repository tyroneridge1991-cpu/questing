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
@PluginDescriptor(name = "Quest Navigator Account Sync", description = "Publishes read-only RuneLite account state to OSRS Quest Navigator.", tags = {"quest", "ironman", "skills", "bank", "inventory", "equipment", "sync"})
public class AccountSyncPlugin extends Plugin
{
    private static final Gson GSON = new GsonBuilder().disableHtmlEscaping().create();
    private static final Path DIR = Path.of(System.getProperty("user.home"), "AppData", "Local", "OSRSQuestNavigator");
    private static final Path FILE = DIR.resolve("account.json");
    private static final Path TEMP = DIR.resolve("account.json.tmp");

    @Inject private Client client;
    @Inject private AccountSyncConfig config;

    @Override protected void startUp() { writeSnapshot(); }
    @Override protected void shutDown() { }

    @Subscribe public void onGameTick(GameTick event) { if (config.syncEnabled()) writeSnapshot(); }
    @Subscribe public void onGameStateChanged(GameStateChanged event) { if (config.syncEnabled() && event.getGameState() == GameState.LOGGED_IN) writeSnapshot(); }
    @Subscribe public void onItemContainerChanged(ItemContainerChanged event) { if (config.syncEnabled()) writeSnapshot(); }

    private void writeSnapshot()
    {
        if (client.getGameState() != GameState.LOGGED_IN) return;
        try
        {
            Files.createDirectories(DIR);
            Map<String,Object> root = new LinkedHashMap<>();
            root.put("schema", 1);
            root.put("timestamp", System.currentTimeMillis());
            Player player = client.getLocalPlayer();
            root.put("username", player == null || player.getName() == null ? "" : player.getName());

            if (player != null)
            {
                WorldPoint p = player.getWorldLocation();
                if (p != null)
                {
                    Map<String,Object> location = new LinkedHashMap<>();
                    location.put("x", p.getX()); location.put("y", p.getY()); location.put("plane", p.getPlane());
                    root.put("location", location);
                }
            }

            Map<String,Object> skills = new LinkedHashMap<>();
            for (Skill skill : Skill.values())
            {
                Map<String,Object> v = new LinkedHashMap<>();
                v.put("level", client.getRealSkillLevel(skill));
                v.put("boosted", client.getBoostedSkillLevel(skill));
                v.put("xp", client.getSkillExperience(skill));
                skills.put(skill.getName().toLowerCase(), v);
            }
            root.put("skills", skills);

            Map<String,String> quests = new LinkedHashMap<>();
            for (Quest quest : Quest.values())
            {
                QuestState state = quest.getState(client);
                quests.put(quest.getName(), state == null ? "UNKNOWN" : state.name());
            }
            root.put("quests", quests);
            root.put("inventory", items(InventoryID.INVENTORY));
            root.put("equipment", items(InventoryID.EQUIPMENT));
            root.put("bank", items(InventoryID.BANK));
            root.put("bankAvailable", client.getItemContainer(InventoryID.BANK) != null);

            Map<String,Object> account = new LinkedHashMap<>();
            account.put("combatLevel", player == null ? 0 : player.getCombatLevel());
            account.put("runEnergy", client.getEnergy());
            root.put("account", account);

            String json = GSON.toJson(root);
            Files.writeString(TEMP, json, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE);
            try { Files.move(TEMP, FILE, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE); }
            catch (AtomicMoveNotSupportedException e) { Files.move(TEMP, FILE, StandardCopyOption.REPLACE_EXISTING); }
        }
        catch (IOException | RuntimeException e) { log.debug("Unable to publish account snapshot", e); }
    }

    private Map<String,Object> items(InventoryID id)
    {
        Map<String,Object> out = new LinkedHashMap<>();
        ItemContainer container = client.getItemContainer(id);
        if (container == null) return out;
        for (int slot = 0; slot < container.size(); slot++)
        {
            Item item = container.getItem(slot);
            if (item == null || item.getId() <= 0 || item.getQuantity() <= 0) continue;
            Map<String,Object> v = new LinkedHashMap<>();
            v.put("id", item.getId()); v.put("quantity", item.getQuantity()); v.put("slot", slot);
            out.put(Integer.toString(slot), v);
        }
        return out;
    }

    @Provides AccountSyncConfig provideConfig(net.runelite.client.config.ConfigManager configManager) { return configManager.getConfig(AccountSyncConfig.class); }

    @ConfigGroup("questnavigatoraccountsync")
    public interface AccountSyncConfig extends Config
    {
        @ConfigItem(keyName = "syncEnabled", name = "Enable account sync", description = "Write read-only account state to the local Quest Navigator file")
        default boolean syncEnabled() { return true; }
    }
}
