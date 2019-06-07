# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

from relstorage.cache.local_database import Database
from relstorage.cache.persistence import sqlite_connect

from relstorage.tests import TestCase
from relstorage.cache.tests import MockOptions

class MockOptionsWithMemoryDB(MockOptions):
    cache_local_dir = ':memory:'

class UpdateTests(TestCase):
    # Tests to specifically cover the cases that
    # UPSERTS or multi-column updates aren't available.

    USE_UPSERT = False
    USE_PAREN_UPDATE = False

    def setUp(self):
        self.options = MockOptionsWithMemoryDB()
        self.connection = sqlite_connect(
            self.options, "pfx-ignored", close_async=False)
        assert self.connection.rs_db_filename == ':memory:', self.connection
        self.db = self._makeOne()

    def tearDown(self):
        # Be sure we can commit; this can be an issue on PyPy
        self.connection.commit()
        self.db.close()

    def _makeOne(self):
        return Database.from_connection(
            self.connection,
            use_upsert=self.USE_UPSERT,
            use_paren_update=self.USE_PAREN_UPDATE
        )

    def test_set_checkpoints(self):
        self.db.update_checkpoints(1, 0)
        self.assertEqual(self.db.checkpoints, (1, 0))

    def test_update_checkpoints_newer(self):
        self.db.update_checkpoints(1, 0)
        self.db.update_checkpoints(2, 1)
        self.assertEqual(self.db.checkpoints, (2, 1))

    def test_update_checkpoints_older(self):
        self.db.update_checkpoints(2, 1)
        self.db.update_checkpoints(1, 0)
        self.assertEqual(self.db.checkpoints, (2, 1))

    def test_move_from_temp_empty(self):
        rows = [
            (0, 0, b'', 0),
            (1, 0, b'', 0)
        ]
        self.db.store_temp(rows)
        self.db.move_from_temp()
        self.assertEqual(dict(self.db.oid_to_tid),
                         {0: 0, 1: 0})

    def test_move_from_temp_mixed_updates(self):
        rows = [
            (0, 1, b'0', 0),
            (1, 1, b'1', 0),
            (2, 1, b'2', 0),
        ]
        self.db.store_temp(rows)
        self.db.move_from_temp()

        new_rows = [
            # 0 goes backwards
            (0, 0, b'-1', 0),
            # 1 stays the same (but we use a different state
            # to verify)
            (1, 1, b'-1', 0),
            # 2 moves forward
            (2, 2, b'2b', 0)
        ]

        self.db.store_temp(new_rows)
        self.db.move_from_temp()

        self.connection.commit()
        self.assertEqual(
            dict(self.db.oid_to_tid),
            {0: 1, 1: 1, 2: 2}
        )

        rows_in_db = list(self.db.fetch_rows_by_priority())
        rows_in_db.sort()
        self.assertEqual(rows_in_db[0], (0, 1, b'0', 1))
        self.assertEqual(rows_in_db[1], (1, 1, b'1', 1))
        self.assertEqual(rows_in_db[2], (2, 2, b'2b', 2))


    def test_trim_to_size_deletes_stale(self):
        rows = [
            (0, 1, b'0', 0),
            (1, 1, b'0', 0),
        ]
        self.db.store_temp(rows)
        self.db.move_from_temp()

        self.db.trim_to_size(
            # It's not trimming for a limit
            10000,
            # But we do know stale things that have to go.
            # OID 1 must be at least TID 2
            {1: 2}
        )
        # Leaving behind only one row
        self.assertEqual(dict(self.db.oid_to_tid), {0: 1})

    def test_trim_to_size_removes_size_oldest_first(self):
        # We delete the oldest, least used, biggest objects first.
        # These are tied on frequency, size, and transaction age.
        # Tie-breaker is OID, which indicates an older object again.
        rows = [
            (0, 1, b'0', 0),
            (1, 1, b'0', 0),
        ]
        self.db.store_temp(rows)
        self.db.move_from_temp()

        self.db.trim_to_size(
            1,
            ()
        )
        self.assertEqual(dict(self.db.oid_to_tid), {1: 1})

    def test_trim_to_size_removes_least_frequent_first(self):
        # We delete the oldest, least used, biggest objects first.
        # The newer object is less frequent than the older, so it goes.
        rows = [
            (0, 1, b'0', 1),
            (1, 1, b'0', 0),
        ]
        self.db.store_temp(rows)
        self.db.move_from_temp()

        self.db.trim_to_size(
            1,
            ()
        )
        self.assertEqual(dict(self.db.oid_to_tid), {0: 1})

    def test_trim_to_size_removes_biggest_first(self):
        # We delete the oldest, least used, biggest objects first.
        # The newer object is bigger, so it goes
        rows = [
            (0, 1, b'0', 0),
            (1, 1, b'00', 0),
        ]
        self.db.store_temp(rows)
        self.db.move_from_temp()

        self.db.trim_to_size(
            1,
            ()
        )
        self.assertEqual(dict(self.db.oid_to_tid), {0: 1})


@unittest.skipIf(not Database.SUPPORTS_UPSERT,
                 "Requires upserts")
class UpsertUpdateTests(UpdateTests):
    USE_UPSERT = True


@unittest.skipIf(not Database.SUPPORTS_PAREN_UPDATE,
                 "Requires paren updates")
class ParenUpdateTests(UpdateTests):
    USE_PAREN_UPDATE = True
