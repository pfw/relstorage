# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2008, 2019 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

"""
Implementation of load methods.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from perfmetrics import Metric
from perfmetrics import metricmethod

from ZODB.POSException import POSKeyError

from ZODB.utils import p64 as int64_to_8bytes
from ZODB.utils import u64 as bytes8_to_int64

from relstorage.cache.interfaces import CacheConsistencyError

logger = __import__('logging').getLogger(__name__)

def _log_keyerror(cursor, adapter, oid_int, reason):
    """
    Log just before raising POSKeyError in load().

    KeyErrors in load() are generally not supposed to happen,
    so this is a good place to gather information.
    """
    logfunc = logger.warning
    msg = ["POSKeyError on oid %d: %s" % (oid_int, reason)]

    if adapter.keep_history:
        tid = adapter.txncontrol.get_tid(cursor)
        if not tid:
            # This happens when initializing a new database or
            # after packing, so it's not a warning.
            logfunc = logger.debug
            msg.append("No previous transactions exist")
        else:
            msg.append("Current transaction is %d" % tid)

        tids = []
        try:
            rows = adapter.dbiter.iter_object_history(cursor, oid_int)
        except KeyError:
            # The object has no history, at least from the point of view
            # of the current database load connection.
            pass
        else:
            for row in rows:
                tids.append(row[0])
                if len(tids) >= 10:
                    break
        msg.append("Recent object tids: %s" % repr(tids))

    else:
        if oid_int == 0:
            # This happens when initializing a new database or
            # after packing, so it's usually not a warning.
            logfunc = logger.debug
        msg.append("history-free adapter")

    logfunc('; '.join(msg))


class Loader(object):

    STORAGE_METHODS = (
        'load',
        'loadBefore',
        'loadSerial',
        'prefetch',
        'getTid',
    )

    __slots__ = (
        'adapter',
        'load_connection',
        'store_connection',
        'cache',
    )

    def __init__(self, adapter, load_connection, store_connection, cache):
        self.adapter = adapter
        self.load_connection = load_connection
        self.store_connection = store_connection
        self.cache = cache

    def __load_using_method(self, meth, argument):
        cursor = self.load_connection.cursor
        try:
            return meth(cursor, argument)
        except CacheConsistencyError:
            logger.exception("Cache consistency error; restarting load")
            self.load_connection.drop()
            raise

    @Metric(method=True, rate=0.1)
    def load(self, oid, version=''):
        # pylint:disable=unused-argument
        oid_int = bytes8_to_int64(oid)
        state, tid_int = self.__load_using_method(self.cache.load, oid_int)

        if tid_int is None:
            _log_keyerror(self.load_connection.cursor,
                          self.adapter,
                          oid_int,
                          "no tid found")
            raise POSKeyError(oid)

        if not state:
            # This can happen if something attempts to load
            # an object whose creation has been undone.
            _log_keyerror(self.load_connection.cursor,
                          self.adapter,
                          oid_int,
                          "creation has been undone")
            raise POSKeyError(oid)
        return state, int64_to_8bytes(tid_int)

    def getTid(self, oid):
        _state, serial = self.load(oid)
        return serial

    def prefetch(self, oids):
        prefetch = self.cache.prefetch
        oid_ints = [bytes8_to_int64(oid) for oid in oids]
        try:
            self.__load_using_method(prefetch, oid_ints)
        except Exception: # pylint:disable=broad-except
            # This could raise self._stale_error, or
            # CacheConsistencyError. Both of those mean that regular loads
            # may fail too, but we don't know what our transaction state is
            # at this time, so we don't want to raise it to the caller.
            logger.exception("Failed to prefetch")

    @Metric(method=True, rate=0.1)
    def loadSerial(self, oid, serial):
        """Load a specific revision of an object"""
        oid_int = bytes8_to_int64(oid)
        tid_int = bytes8_to_int64(serial)

        # If we've got this state cached exactly,
        # use it. No need to poll or anything like that first;
        # polling is unlikely to get us the state we want.
        # If the data happens to have been removed from the database,
        # due to a pack, this won't detect it if it was already cached
        # and the pack happened somewhere else. This method is
        # only used for conflict resolution, though, and we
        # shouldn't be able to get to that point if the root revision
        # went missing, right? Packing periodically takes the same locks we
        # want to take for committing.
        state = self.cache.loadSerial(oid_int, tid_int)
        if state:
            return state

        state = self.adapter.mover.load_revision(
            self.load_connection.cursor, oid_int, tid_int)
        if state is None and self.store_connection:
            # Allow loading data from later transactions
            # for conflict resolution.
            state = self.adapter.mover.load_revision(
                self.store_connection.cursor, oid_int, tid_int)

        if state is None or not state:
            raise POSKeyError(oid)
        return state

    @Metric(method=True, rate=0.1)
    def loadBefore(self, oid, tid):
        """Return the most recent revision of oid before tid committed."""
        oid_int = bytes8_to_int64(oid)

        if self.store_connection:
            # Allow loading data from later transactions
            # for conflict resolution.
            cursor = self.store_connection.cursor
        else:
            cursor = self.load_connection.cursor
        if not self.adapter.mover.exists(cursor, oid_int):
            raise POSKeyError(oid)

        state, start_tid = self.adapter.mover.load_before(
            cursor, oid_int, bytes8_to_int64(tid))

        if start_tid is None:
            return None

        if state is None:
            # This can happen if something attempts to load
            # an object whose creation has been undone, see load()
            # This change fixes the test in
            # TransactionalUndoStorage.checkUndoCreationBranch1
            # self._log_keyerror doesn't work here, only in certain states.
            raise POSKeyError(oid)
        end_int = self.adapter.mover.get_object_tid_after(
            cursor, oid_int, start_tid)
        if end_int is not None:
            end = int64_to_8bytes(end_int)
        else:
            end = None

        return state, int64_to_8bytes(start_tid), end


class BlobLoader(object):

    STORAGE_METHODS = (
        'loadBlob',
        'openCommittedBlobFile',
    )

    def __init__(self, load_connection, blobhelper):
        self.load_connection = load_connection
        self.blobhelper = blobhelper

    @metricmethod
    def loadBlob(self, oid, serial):
        """Return the filename of the Blob data for this OID and serial.

        Returns a filename.

        Raises POSKeyError if the blobfile cannot be found.
        """
        cursor = self.load_connection.cursor
        return self.blobhelper.loadBlob(cursor, oid, serial)

    @metricmethod
    def openCommittedBlobFile(self, oid, serial, blob=None):
        """
        Return a file for committed data for the given object id and serial

        If a blob is provided, then a BlobFile object is returned,
        otherwise, an ordinary file is returned. In either case, the
        file is opened for binary reading.

        This method is used to allow storages that cache blob data to
        make sure that data are available at least long enough for the
        file to be opened.
        """
        cursor = self.load_connection.cursor
        return self.blobhelper.openCommittedBlobFile(
            cursor, oid, serial, blob=blob)