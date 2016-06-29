# Copyright 2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
import time

from concurrent.futures import ThreadPoolExecutor

from tests import unittest
from tests import TransferCoordinatorWithInterrupt
from s3transfer.futures import TransferCoordinator
from s3transfer.manager import TransferCoordinatorCanceler


class FutureResultException(Exception):
    pass


class TestTransferCoordinatorCanceler(unittest.TestCase):
    def setUp(self):
        self.canceler = TransferCoordinatorCanceler()

    def sleep_then_announce_done(self, transfer_coordinator, sleep_time):
        time.sleep(sleep_time)
        transfer_coordinator.set_result('done')
        transfer_coordinator.announce_done()

    def assert_coordinator_is_cancelled(self, transfer_coordinator):
        self.assertEqual(transfer_coordinator.status, 'cancelled')

    def test_add_transfer_coordinator(self):
        transfer_coordinator = TransferCoordinator()
        # Add the transfer coordinator
        self.canceler.add_transfer_coordinator(transfer_coordinator)
        # Ensure that is tracked.
        self.assertEqual(
            self.canceler.tracked_transfer_coordinators,
            set([transfer_coordinator]))

    def test_remove_transfer_coordinator(self):
        transfer_coordinator = TransferCoordinator()
        # Add the coordinator
        self.canceler.add_transfer_coordinator(transfer_coordinator)
        # Now remove the coordinator
        self.canceler.remove_transfer_coordinator(transfer_coordinator)
        # Make sure that it is no longer getting tracked.
        self.assertEqual(self.canceler.tracked_transfer_coordinators, set())

    def test_cancel(self):
        transfer_coordinator = TransferCoordinator()
        # Add the transfer coordinator
        self.canceler.add_transfer_coordinator(transfer_coordinator)
        # Cancel with the canceler
        self.canceler.cancel()
        # Check that coordinator got canceled
        self.assert_coordinator_is_cancelled(transfer_coordinator)

    def test_wait_for_done_transfer_coordinators(self):
        # Create a coordinator and add it to the canceler
        transfer_coordinator = TransferCoordinator()
        self.canceler.add_transfer_coordinator(transfer_coordinator)

        sleep_time = 0.02
        with ThreadPoolExecutor(max_workers=1) as executor:
            # In a seperate thread sleep and then set the transfer coordinator
            # to done after sleeping.
            start_time = time.time()
            executor.submit(
                self.sleep_then_announce_done, transfer_coordinator,
                sleep_time)
            # Now call wait to wait for the transfer coordinator to be done.
            self.canceler.wait()
            end_time = time.time()
            wait_time = end_time - start_time
        # The time waited should not be less than the time it took to sleep in
        # the seperate thread because the wait ending should be dependent on
        # the sleeping thread announcing that the transfer coordinator is done.
        self.assertTrue(sleep_time <= wait_time)

    def test_wait_does_not_propogate_exceptions_from_result(self):
        transfer_coordinator = TransferCoordinator()
        transfer_coordinator.set_exception(FutureResultException())
        transfer_coordinator.announce_done()
        try:
            self.canceler.wait()
        except FutureResultException as e:
            self.fail('%s should not have been raised.' % e)

    def test_wait_can_be_interrupted(self):
        inject_interrupt_coordinator = TransferCoordinatorWithInterrupt()
        self.canceler.add_transfer_coordinator(inject_interrupt_coordinator)
        with self.assertRaises(KeyboardInterrupt):
            self.canceler.wait()
