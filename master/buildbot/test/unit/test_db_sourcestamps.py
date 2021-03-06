# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db import sourcestamps
from buildbot.test.util import db, connector_component

class TestSourceStampsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            db.RealDatabaseMixin,
            unittest.TestCase):

    def setUp(self):
        self.setUpRealDatabase()
        self.setUpConnectorComponent(self.db_url)

        # add the .sourcestamps attribute
        self.db.sourcestamps = sourcestamps.SourceStampsConnectorComponent(self.db)

        # set up the tables we'll need, following links where ForeignKey
        # constraints are in place.
        def thd(engine):
            self.db.model.changes.create(bind=engine)
            self.db.model.patches.create(bind=engine)
            self.db.model.sourcestamp_changes.create(bind=engine)
            self.db.model.sourcestamps.create(bind=engine)
        return self.db.pool.do_with_engine(thd)

    def tearDown(self):
        self.tearDownConnectorComponent()
        self.tearDownRealDatabase()

    # tests

    def test_createSourceStamp_simple(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.sourcestamps.createSourceStamp('production', 'abdef',
                'test://repo', 'stamper'))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.project)
                         for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', None, 'test://repo', 'stamper') ])

                # .. and no sourcestamp_changes
                ssc_tbl = self.db.model.sourcestamp_changes
                r = conn.execute(ssc_tbl.select())
                rows = [ 1 for row in r.fetchall() ]
                self.assertEqual(rows, [])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createSourceStamp_changes(self):
        # add some sample changes for referential integrity
        def thd(conn):
            stmt = self.db.model.changes.insert()
            conn.execute(stmt, [
              dict(changeid=3, author="three", comments="3", is_dir=False,
                  branch="trunk", revision="0e92a098b",
                  when_timestamp=266738404, revlink='lnk', category='devel',
                  repository='git://warner', project='Buildbot'),
              dict(changeid=4, author="four", comments="4", is_dir=False,
                  branch="trunk", revision="0e92a098b",
                  when_timestamp=266738404, revlink='lnk', category='devel',
                  repository='git://warner', project='Buildbot'),
            ])
        d = self.db.pool.do(thd)

        d.addCallback(lambda _ :
            self.db.sourcestamps.createSourceStamp('production', 'abdef',
                'test://repo', 'stamper', changeids=[3,4]))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.project)
                         for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', None, 'test://repo', 'stamper') ])

                # .. and two sourcestamp_changes
                ssc_tbl = self.db.model.sourcestamp_changes
                r = conn.execute(ssc_tbl.select())
                rows = [ (row.sourcestampid, row.changeid) for row in r.fetchall() ]
                self.assertEqual(sorted(rows), [ (ssid, 3), (ssid, 4) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_createSourceStamp_patch(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.sourcestamps.createSourceStamp('production', 'abdef',
                'test://repo', 'stamper', patch_body='my patch', patch_level=3,
                patch_subdir='master/'))
        def check(ssid):
            def thd(conn):
                # should see one sourcestamp row
                ss_tbl = self.db.model.sourcestamps
                r = conn.execute(ss_tbl.select())
                rows = [ (row.id, row.branch, row.revision,
                          row.patchid, row.repository, row.project)
                         for row in r.fetchall() ]
                patchid = row.patchid
                self.assertNotEqual(patchid, None)
                self.assertEqual(rows,
                    [ ( ssid, 'production', 'abdef', patchid, 'test://repo', 'stamper') ])

                # .. and a single patch
                patches_tbl = self.db.model.patches
                r = conn.execute(patches_tbl.select())
                rows = [ (row.id, row.patchlevel, row.patch_base64, row.subdir)
                         for row in r.fetchall() ]
                self.assertEqual(rows, [(patchid, 3, 'bXkgcGF0Y2g=', 'master/')])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d
