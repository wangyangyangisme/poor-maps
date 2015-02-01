# -*- coding: utf-8 -*-

# Copyright (C) 2014 Osmo Salomaa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""An application to display maps and stuff."""

import math
import os
import poor
import pyotherside
import queue
import sys
import threading
import time

__all__ = ("Application",)


class Application:

    """An application to display maps and stuff."""

    def __init__(self):
        """Initialize a :class:`Application` instance."""
        self.basemap = None
        self._download_queue = queue.Queue()
        self.geocoder = None
        self.guide = None
        self.history = poor.HistoryManager()
        self.narrative = poor.Narrative()
        self.overlays = []
        self.router = None
        self._tilecollection = poor.TileCollection()
        self._timestamp = int(time.time()*1000)
        self._init_download_threads()
        self.set_basemap(poor.conf.basemap)
        self.add_overlays(*poor.conf.overlays)
        self.set_geocoder(poor.conf.geocoder)
        self.set_guide(poor.conf.guide)
        self.set_router(poor.conf.router)
        poor.cache.purge_async()

    def add_overlays(self, *overlays):
        """Add overlay providers from strings `overlays`."""
        for overlay in overlays:
            try:
                self.overlays.append(poor.TileSource(overlay))
                self.overlays.sort(key=lambda x: x.z)
                poor.conf.set_add("overlays", overlay)
                self._tilecollection.reset()
            except Exception as error:
                print("Failed to load overlay '{}': {}"
                      .format(overlay, str(error)),
                      file=sys.stderr)

    def _init_download_threads(self):
        """Initialize map tile download threads."""
        # tilesource.ConnectionPool limits the actual amount of
        # connections per host. This thread count should be greater
        # than that to allow tiles from different hosts (basemap, overlays)
        # to be downloaded at the same time.
        for i in range(16):
            threading.Thread(target=self._process_download_queue,
                             daemon=True).start()

    def _process_download_queue(self):
        """Monitor download queue and feed items for update."""
        while True:
            args, timestamp = self._download_queue.get()
            if timestamp == self._timestamp:
                # Only download tiles queued in the latest update.
                self._update_tile(*args, timestamp=timestamp)
            self._download_queue.task_done()

    def remove_overlays(self, *overlays):
        """Remove overlay providers from strings `overlays`."""
        if not overlays:
            overlays = [x.id for x in self.overlays]
        for i in reversed(range(len(self.overlays))):
            if self.overlays[i].id in overlays:
                self.overlays.pop(i)
        for overlay in overlays:
            poor.conf.set_remove("overlays", overlay)
        self._tilecollection.reset()

    def set_basemap(self, basemap):
        """Set basemap from string `basemap`."""
        try:
            self.basemap = poor.TileSource(basemap)
            poor.conf.basemap = basemap
            self._tilecollection.reset()
        except Exception as error:
            print("Failed to load basemap '{}': {}"
                  .format(basemap, str(error)),
                  file=sys.stderr)
            if self.basemap is None:
                default = poor.conf.get_default("basemap")
                if default != basemap:
                    self.set_basemap(default)

    def set_geocoder(self, geocoder):
        """Set geocoding provider from string `geocoder`."""
        try:
            self.geocoder = poor.Geocoder(geocoder)
            poor.conf.geocoder = geocoder
        except Exception as error:
            print("Failed to load geocoder '{}': {}"
                  .format(geocoder, str(error)),
                  file=sys.stderr)
            if self.geocoder is None:
                default = poor.conf.get_default("geocoder")
                if default != geocoder:
                    self.set_geocoder(default)

    def set_guide(self, guide):
        """Set place guide provider from string `guide`."""
        try:
            self.guide = poor.Guide(guide)
            poor.conf.guide = guide
        except Exception as error:
            print("Failed to load guide '{}': {}"
                  .format(guide, str(error)),
                  file=sys.stderr)
            if self.guide is None:
                default = poor.conf.get_default("guide")
                if default != guide:
                    self.set_guide(default)

    def set_router(self, router):
        """Set routing provider from string `router`."""
        try:
            self.router = poor.Router(router)
            poor.conf.router = router
        except Exception as error:
            print("Failed to load router '{}': {}"
                  .format(router, str(error)),
                  file=sys.stderr)
            if self.router is None:
                default = poor.conf.get_default("router")
                if default != router:
                    self.set_router(default)

    def _update_tile(self, tilesource, xmin, xmax, ymin, ymax, zoom,
                     display_zoom, tile, timestamp):

        """Download missing tile and ask QML to render it."""
        key = tilesource.tile_key(tile)
        item = self._tilecollection.get(key)
        if item is not None:
            return pyotherside.send("show-tile", item.uid)
        path = tilesource.download(tile)
        if path is None: return
        # Abort if map moved out of view during download.
        if timestamp != self._timestamp: return
        uri = (poor.util.path2uri(path) if os.path.isabs(path) else path)
        corners = tilesource.tile_corners(tile)
        item = self._tilecollection.get_free(
            key, xmin, xmax, ymin, ymax, display_zoom, corners)
        pyotherside.send("render-tile", dict(display_zoom=display_zoom,
                                             nex=corners[0][0],
                                             nwx=corners[3][0],
                                             nwy=corners[3][1],
                                             scale=tilesource.scale,
                                             smooth=tilesource.smooth,
                                             swy=corners[2][1],
                                             type=tilesource.type,
                                             uid=item.uid,
                                             uri=uri,
                                             z=tilesource.z,
                                             zoom=zoom))

    def update_tiles(self, xmin, xmax, ymin, ymax, zoom):
        """Download missing tiles and ask QML to render them."""
        self._tilecollection.sort()
        self._timestamp = int(time.time()*1000)
        total_tiles = 0
        for tilesource in [self.basemap] + self.overlays:
            # For scales above one, get tile from an above zoom level.
            z = int(zoom - math.log2(tilesource.scale))
            for tile in tilesource.list_tiles(xmin, xmax, ymin, ymax, z):
                args = (tilesource, xmin, xmax, ymin, ymax, z, zoom, tile)
                self._download_queue.put((args, self._timestamp))
                total_tiles += 1
        # Keep a few screenfulls of tiles in memory.
        total_tiles = math.ceil(total_tiles / (1 + len(self.overlays)))
        size = (3 + len(self.overlays)) * total_tiles
        if self._tilecollection.size < size:
            self._tilecollection.grow(size)
