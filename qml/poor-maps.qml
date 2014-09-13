/* -*- coding: utf-8-unix -*-
 *
 * Copyright (C) 2014 Osmo Salomaa
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import QtQuick 2.0
import Sailfish.Silica 1.0
import "."

ApplicationWindow {
    id: app
    allowedOrientations: Orientation.All
    cover: undefined
    initialPage: Page {
        id: mapPage
        // XXX: Map gestures don't work right in landscape.
        // http://bugreports.qt-project.org/browse/QTBUG-40799
        allowedOrientations: Orientation.Portrait
        Map { id: map }
    }
    // TODO: Add cover.status when we have a cover.
    property bool running: applicationActive
    PositionSource { id: gps }
    Python { id: py }
    Component.onCompleted: {
        py.setHandler("render-tile", map.renderTile);
        py.setHandler("show-tile", map.showTile);
    }
    onApplicationActiveChanged: {
        if (!app.applicationActive && py.ready) {
            py.call_sync("poor.conf.write", []);
            py.call_sync("poor.app.history.write", []);
        }
    }
}
