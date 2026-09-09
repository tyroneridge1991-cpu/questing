"""External, read-only route projection helpers for the OSRS Navigator.

This module deliberately does not send input to RuneLite. It turns a known
screen-space destination into a lightweight sequence of guidance markers.
World-coordinate/A* routing can be plugged in later without changing the
overlay contract.
"""
from math import hypot


def simplify(points, min_step=10.0):
    if not points:
        return []
    out=[points[0]]
    for p in points[1:]:
        if hypot(p[0]-out[-1][0], p[1]-out[-1][1]) >= min_step:
            out.append(p)
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out


def screen_route(start, destination, spacing=28.0, max_markers=40):
    """Return evenly spaced screen-space guidance markers.

    These are intentionally called markers rather than true world tiles: an
    external screen-only app cannot know the client's camera projection or
    collision map with the accuracy RuneLite's Perspective API can provide.
    """
    if not start or not destination:
        return []
    x0,y0=start; x1,y1=destination
    dist=hypot(x1-x0,y1-y0)
    count=max(1,min(max_markers,int(dist/max(8.0,spacing))))
    pts=[]
    for i in range(1,count+1):
        t=i/count
        pts.append((x0+(x1-x0)*t,y0+(y1-y0)*t))
    return simplify(pts, max(6.0,spacing*0.55))


def guidance_text(distance_px, marker_count):
    if marker_count <= 0:
        return "No route projected"
    return f"Route projected • {marker_count} guidance tiles • {int(distance_px)} px"
