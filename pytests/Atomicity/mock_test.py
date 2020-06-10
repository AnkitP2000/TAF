import time

from basetestcase import BaseTestCase
from sdk_client3 import SDKClient

import com.couchbase.test.transactions.SimpleTransaction as Transaction
from reactor.util.function import Tuples

"""
Basic test cases with commit,rollback scenarios
"""


class basic_ops(BaseTestCase):
    def setUp(self):
        super(basic_ops, self).setUp()
        nodes_init = self.cluster.servers[1:self.nodes_init] \
            if self.nodes_init != 1 else []
        self.task.rebalance([self.cluster.master], nodes_init, [])
        self.cluster.nodes_in_cluster.extend([self.cluster.master]+nodes_init)
        self.bucket_util.add_rbac_user()

        if self.default_bucket:
            self.bucket_util.create_default_bucket(
                replica=self.num_replicas,
                compression_mode=self.compression_mode,
                ram_quota=100, bucket_type=self.bucket_type)

        time.sleep(10)
        self.client = SDKClient([self.cluster.master],
                                self.bucket_util.buckets[0])
        self.__durability_level()

        self.operation = self.input.param("operation", "afterAtrPending")
        self.always_fail = self.input.param("fail", False)
        self.verify = self.input.param("verify", True)

        # create load
        self.value = {'value': 'value1'}
        self.content = self.client.translate_to_json_object(self.value)

        self.docs = []
        self.keys = []
        for i in range(self.num_items):
            key = "test_docs-" + str(i)
            doc = Tuples.of(key, self.content)
            self.keys.append(key)
            self.docs.append(doc)

        self.transaction_config = Transaction().createTransactionConfig(
            self.transaction_timeout, self.durability)
        self.log.info("==========Finished Basic_ops base setup========")

    def tearDown(self):
        self.client.close()
        super(basic_ops, self).tearDown()

    def __durability_level(self):
        if self.durability_level == "MAJORITY":
            self.durability = 1
        elif self.durability_level == "MAJORITY_AND_PERSIST_ON_MASTER":
            self.durability = 2
        elif self.durability_level == "PERSIST_TO_MAJORITY":
            self.durability = 3
        elif self.durability_level == "ONLY_NONE":
            self.durability = 4
        else:
            self.durability = 0

    def set_exception(self, exception):
        raise BaseException(exception)

    def test_txnwithhooks(self):
        # transaction load
        if "Atr" in self.operation:
            exception = Transaction().MockRunTransaction(
                self.client.cluster, self.transaction_config,
                self.client.collection, self.docs, "create",
                self.transaction_commit,
                self.operation, 1)
        else:
            if "Replace" in self.operation:
                exception = Transaction().MockRunTransaction(
                    self.client.cluster, self.transaction_config,
                    self.client.collection, self.docs, self.keys, [],
                    self.transaction_commit, self.operation, self.keys[-1],
                    self.always_fail)
                self.value = {'mutated': 1, 'value': 'value1'}
                self.content = self.client.translate_to_json_object(self.value)
            else:
                exception = Transaction().MockRunTransaction(
                    self.client.cluster, self.transaction_config,
                    self.client.collection, self.docs, [], [],
                    self.transaction_commit, self.operation, self.keys[-1],
                    self.always_fail)

            if "Remove" in self.operation:
                exception = Transaction().MockRunTransaction(
                    self.client.cluster, self.transaction_config,
                    self.client.collection, [], [], self.keys,
                    self.transaction_commit, self.operation, self.keys[-1],
                    self.always_fail)

        # verify the values
        for key in self.keys:
            result = self.client.read(key)
            if "Remove" in self.operation \
                    or self.transaction_commit is False \
                    or self.verify is False:
                if result['status']:
                    actual_val = self.client.translate_to_json_object(
                        result['value'])
                    self.log.info("Actual value for key %s is %s"
                                  % (key, actual_val))
                    msg = \
                        "Key '%s' should be deleted but present in the bucket"\
                        % key
                    self.set_exception(msg)
            else:
                actual_val = self.client.translate_to_json_object(
                    result['value'])
                if self.content != actual_val:
                    self.log.info("Key %s Actual: %s, Expected: %s"
                                  % (key, actual_val, self.content))
                    self.set_exception("Mismatch in doc content")

        if exception and self.fail is not True:
            self.set_exception(exception)
