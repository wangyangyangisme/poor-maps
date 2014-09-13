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
import QtPositioning 5.0

Timer {
    id: timer
    interval: 3000
    repeat: true
    running: app.running && map.hasRoute
    triggeredOnStart: true
    property var coordinatePrev: QtPositioning.coordinate(0, 0)
    onRunningChanged: {
        // Always update after changing timer state.
        timer.coordinatePrev.longitude = 0;
        timer.coordinatePrev.latitude = 0;
    }
    onTriggered: {
        // Query maneuver narrative from Python and update status.
        if (!py.ready) return;
        if (!map.hasRoute) return;
        if (map.position.coordinate.distanceTo(timer.coordinatePrev) < 10) return;
        var x = map.position.coordinate.longitude;
        var y = map.position.coordinate.latitude;
        py.call("poor.app.narrative.get_display", [x, y], function(status) {
            map.setRoutingStatus(status);
            timer.coordinatePrev.longitude = map.position.coordinate.longitude;
            timer.coordinatePrev.latitude = map.position.coordinate.latitude;
        });
    }
}
