/*****************************************************************************

  Copyright (c) 2003 Zope Foundation and Contributors.
  All Rights Reserved.

  This software is subject to the provisions of the Zope Public License,
  Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
  THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
  WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
  WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
  FOR A PARTICULAR PURPOSE

 ****************************************************************************/

/* Support routines for the doubly-linked list of cached objects.

The cache stores a headed, doubly-linked, circular list of persistent
objects, with space for the pointers allocated in the objects themselves.
The cache stores the distinguished head of the list, which is not a valid
persistent object.  The other list members are non-ghost persistent
objects, linked in LRU (least-recently used) order.

The r_next pointers traverse the ring starting with the least recently used
object.  The r_prev pointers traverse the ring starting with the most
recently used object.

Obscure:  While each object is pointed at twice by list pointers (once by
its predecessor's r_next, again by its successor's r_prev), the refcount
on the object is bumped only by 1.  This leads to some possibly surprising
sequences of incref and decref code.  Note that since the refcount is
bumped at least once, the list does hold a strong reference to each
object in it.
*/

typedef struct CPersistentRing_struct {
    struct CPersistentRing_struct* r_prev;
    struct CPersistentRing_struct* r_next;
    void* r_parent;
    void* user_data;
    uint_fast64_t frequency;
    uint_fast64_t len;
    uint_fast64_t max_len;
} CPersistentRing;

/* The list operations here take constant time independent of the
 * number of objects in the list:
 */

/* Add elt as the most recently used object.  elt must not already be
 * in the list, although this isn't checked.
 */
int ring_add(CPersistentRing *ring, CPersistentRing *elt);

/* Remove elt from the list.  elt must already be in the list, although
 * this isn't checked.
 */
void ring_del(CPersistentRing* ring, CPersistentRing *elt);

/* elt must already be in the list, although this isn't checked.  It's
 * unlinked from its current position, and relinked into the list as the
 * most recently used object (which is arguably the tail of the list
 * instead of the head -- but the name of this function could be argued
 * either way).  This is equivalent to
 *
 *     ring_del(elt);
 *     ring_add(ring, elt);
 *
 * but may be a little quicker.
 */
void ring_move_to_head(CPersistentRing *ring, CPersistentRing *elt);



int ring_move_to_head_from_foreign(CPersistentRing* current_ring,
                                   CPersistentRing* new_ring,
                                   CPersistentRing* elt);


int lru_probation_on_hit(CPersistentRing* probation_ring,
                         CPersistentRing* protected_ring,
                         CPersistentRing* entry);


int lru_update_mru(CPersistentRing* ring,
                    CPersistentRing* entry,
                    uint_fast64_t old_entry_size,
                    uint_fast64_t new_entry_size);


CPersistentRing eden_add(CPersistentRing* eden_ring,
                         CPersistentRing* protected_ring,
                         CPersistentRing* probation_ring,
                         CPersistentRing* entry);
void lru_on_hit(CPersistentRing* ring, CPersistentRing* entry);
