import datetime
import logging
import os
import time
import traceback
import unittest
import inspect

from BucketLib.bucket import Bucket
from Cb_constants import ClusterRun, CbServer
from couchbase_helper.cluster import ServerTasks
from TestInput import TestInputSingleton
from couchbase_helper.durability_helper import BucketDurability
from membase.api.rest_client import RestHelper, RestConnection
from bucket_utils.bucket_ready_functions import BucketUtils
from cluster_utils.cluster_ready_functions import ClusterUtils, CBCluster
from remote.remote_util import RemoteMachineShellConnection
from Jython_tasks.task_manager import TaskManager
from cb_tools.cb_cli import CbCli

from security_config import trust_all_certs
from test_summary import TestSummary


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.input = TestInputSingleton.input

        # Framework specific parameters
        self.log_level = self.input.param("log_level", "info").upper()
        self.infra_log_level = self.input.param("infra_log_level",
                                                "error").upper()
        self.skip_setup_cleanup = self.input.param("skip_setup_cleanup", False)
        self.tear_down_while_setup = self.input.param("tear_down_while_setup",
                                                      True)
        self.test_timeout = self.input.param("test_timeout", 3600)
        self.thread_to_use = self.input.param("threads_to_use", 10)
        self.case_number = self.input.param("case_number", 0)
        # End of framework parameters

        # Cluster level info settings
        self.log_info = self.input.param("log_info", None)
        self.log_location = self.input.param("log_location", None)
        self.stat_info = self.input.param("stat_info", None)
        self.port = self.input.param("port", None)
        self.port_info = self.input.param("port_info", None)
        self.servers = self.input.servers
        self.__cb_clusters = []
        self.num_servers = self.input.param("servers", len(self.servers))
        self.primary_index_created = False
        self.index_quota_percent = self.input.param("index_quota_percent",
                                                    None)
        self.gsi_type = self.input.param("gsi_type", 'plasma')
        # CBAS setting
        self.jre_path = self.input.param("jre_path", None)
        self.enable_dp = self.input.param("enable_dp", False)
        # End of cluster info parameters

        # Bucket specific params
        self.bucket_type = self.input.param("bucket_type",
                                            Bucket.Type.MEMBASE)
        self.bucket_size = self.input.param("bucket_size", None)
        self.bucket_lww = self.input.param("lww", True)
        self.bucket_replica_index = self.input.param("bucket_replica_index",
                                                     1)
        self.bucket_eviction_policy = \
            self.input.param("bucket_eviction_policy",
                             Bucket.EvictionPolicy.VALUE_ONLY)
        self.bucket_time_sync = self.input.param("bucket_time_sync", False)
        self.standard_buckets = self.input.param("standard_buckets", 1)
        if self.standard_buckets > 10:
            self.bucket_util.change_max_buckets(self.standard_buckets)
        self.num_replicas = self.input.param("replicas", 1)
        self.active_resident_threshold = \
            int(self.input.param("active_resident_threshold", 100))
        self.compression_mode = \
            self.input.param("compression_mode",
                             Bucket.CompressionMode.PASSIVE)
        self.bucket_storage = self.input.param(
            "bucket_storage", Bucket.StorageBackend.couchstore)
        if self.bucket_storage == Bucket.StorageBackend.magma:
            self.bucket_eviction_policy = Bucket.EvictionPolicy.FULL_EVICTION
        self.bucket_durability_level = self.input.param(
            "bucket_durability", Bucket.DurabilityLevel.NONE).upper()
        self.bucket_purge_interval = self.input.param("bucket_purge_interval",
                                                      1)
        self.bucket_durability_level = \
            BucketDurability[self.bucket_durability_level]
        # End of bucket parameters

        # Doc specific params
        self.key = self.input.param("key", "test_docs")
        self.key_size = self.input.param("key_size", 8)
        self.doc_size = self.input.param("doc_size", 256)
        self.sub_doc_size = self.input.param("sub_doc_size", 10)
        self.doc_type = self.input.param("doc_type", "json")
        self.num_items = self.input.param("num_items", 100000)
        self.target_vbucket = self.input.param("target_vbucket", None)
        self.maxttl = self.input.param("maxttl", 0)
        # End of doc specific parameters

        # Transactions parameters
        self.transaction_timeout = self.input.param("transaction_timeout", 100)
        self.transaction_commit = self.input.param("transaction_commit", True)
        self.update_count = self.input.param("update_count", 1)
        self.sync = self.input.param("sync", True)
        self.default_bucket = self.input.param("default_bucket", True)
        self.num_buckets = self.input.param("num_buckets", 0)
        self.atomicity = self.input.param("atomicity", False)
        self.defer = self.input.param("defer", False)
        # end of transaction parameters

        # Client specific params
        self.sdk_client_type = self.input.param("sdk_client_type", "java")
        self.sdk_compression = self.input.param("sdk_compression", True)
        self.replicate_to = self.input.param("replicate_to", 0)
        self.persist_to = self.input.param("persist_to", 0)
        self.sdk_retries = self.input.param("sdk_retries", 5)
        self.sdk_timeout = self.input.param("sdk_timeout", 5)
        self.durability_level = self.input.param("durability", "").upper()
        # Doc Loader Params
        self.process_concurrency = self.input.param("process_concurrency", 8)
        self.batch_size = self.input.param("batch_size", 20)
        self.ryow = self.input.param("ryow", False)
        self.check_persistence = self.input.param("check_persistence", False)
        # End of client specific parameters

        # initial number of items in the cluster
        self.services_init = self.input.param("services_init", None)
        self.nodes_init = self.input.param("nodes_init", 1)
        self.nodes_in = self.input.param("nodes_in", 1)
        self.nodes_out = self.input.param("nodes_out", 1)
        self.services_in = self.input.param("services_in", None)
        self.forceEject = self.input.param("forceEject", False)
        self.wait_timeout = self.input.param("wait_timeout", 60)
        self.dgm_run = self.input.param("dgm_run", False)
        self.verify_unacked_bytes = \
            self.input.param("verify_unacked_bytes", False)
        self.disabled_consistent_view = \
            self.input.param("disabled_consistent_view", None)
        self.rebalanceIndexWaitingDisabled = \
            self.input.param("rebalanceIndexWaitingDisabled", None)
        self.rebalanceIndexPausingDisabled = \
            self.input.param("rebalanceIndexPausingDisabled", None)
        self.maxParallelIndexers = \
            self.input.param("maxParallelIndexers", None)
        self.maxParallelReplicaIndexers = \
            self.input.param("maxParallelReplicaIndexers", None)
        self.quota_percent = self.input.param("quota_percent", None)
        self.skip_buckets_handle = self.input.param("skip_buckets_handle",
                                                    False)
        self.use_https = self.input.param("use_https", False)
        self.enforce_tls = self.input.param("enforce_tls", False)
        if self.use_https:
            CbServer.use_https = True
            trust_all_certs()

        # Initiate logging variables
        self.log = logging.getLogger("test")
        self.infra_log = logging.getLogger("infra")

        self.cleanup_pcaps()
        self.collect_pcaps = self.input.param("collect_pcaps", False)
        if self.collect_pcaps:
            self.start_collect_pcaps()

        # variable for log collection using cbCollect
        self.get_cbcollect_info = TestInputSingleton.input.param(
            "get-cbcollect-info", False)

        # Configure loggers
        self.log.setLevel(self.log_level)
        self.infra_log.setLevel(self.infra_log_level)

        # Support lib objects for testcase execution
        self.task_manager = TaskManager(self.thread_to_use)
        self.task = ServerTasks(self.task_manager)
        # End of library object creation

        self.cleanup = False
        self.nonroot = False
        self.test_failure = None
        self.summary = TestSummary(self.log)

        # Populate memcached_port in case of cluster_run
        cluster_run_base_port = ClusterRun.port
        if int(self.input.servers[0].port) == ClusterRun.port:
            for server in self.input.servers:
                server.port = cluster_run_base_port
                cluster_run_base_port += 1
                # If not defined in node.ini under 'memcached_port' section
                if server.memcached_port is CbServer.memcached_port:
                    server.memcached_port = \
                        ClusterRun.memcached_port \
                        + (2 * (int(server.port) - ClusterRun.port))

        self.__log_setup_status("started")
        if len(self.input.clusters) > 1:
            # Multi cluster setup
            counter = 1
            for _, nodes in self.input.clusters.iteritems():
                self.__cb_clusters.append(CBCluster(name="C%s" % counter,
                                                    servers=nodes))
                counter += 1
        else:
            # Single cluster
            self.cluster = CBCluster(servers=self.servers)
            self.__cb_clusters.append(self.cluster)
            self.cluster_util = ClusterUtils(self.cluster, self.task_manager)

            self.bucket_util = BucketUtils(self.cluster, self.cluster_util,
                                           self.task)

        for cluster in self.__cb_clusters:
            shell = RemoteMachineShellConnection(cluster.master)
            self.os_info = shell.extract_remote_info().type.lower()
            if self.os_info != 'windows':
                if cluster.master.ssh_username != "root":
                    self.nonroot = True
                    shell.disconnect()
                    break
            shell.disconnect()

        """ some tests need to bypass checking cb server at set up
            to run installation """
        self.skip_init_check_cbserver = \
            self.input.param("skip_init_check_cbserver", False)

        try:
            if self.skip_setup_cleanup:
                self.bucket_util.get_all_buckets()
                return
            self.services_map = None

            self.__log_setup_status("started")
            for cluster in self.__cb_clusters:
                if not self.skip_buckets_handle \
                        and not self.skip_init_check_cbserver:
                    self.log.debug("Cleaning up cluster")
                    cluster_util = ClusterUtils(cluster, self.task_manager)
                    bucket_util = BucketUtils(cluster, cluster_util,
                                              self.task)
                    cluster_util.cluster_cleanup(bucket_util)

            # avoid any cluster operations in setup for new upgrade
            #  & upgradeXDCR tests
            if str(self.__class__).find('newupgradetests') != -1 or \
                    str(self.__class__).find('upgradeXDCR') != -1 or \
                    str(self.__class__).find('Upgrade_EpTests') != -1 or \
                    self.skip_buckets_handle:
                self.log.warning(
                    "Any cluster operation in setup will be skipped")
                self.primary_index_created = True
                self.__log_setup_status("finished")
                return
            # avoid clean up if the previous test has been tear down
            if self.case_number == 1 or self.case_number > 1000:
                if self.case_number > 1000:
                    self.log.warn(
                        "TearDown for previous test failed. will retry..")
                    self.case_number -= 1000
                self.cleanup = True
                if not self.skip_init_check_cbserver:
                    self.tearDownEverything()
                    self.tear_down_while_setup = False
            if not self.skip_init_check_cbserver:
                for cluster in self.__cb_clusters:
                    self.log.info("Initializing cluster")
                    cluster_util = ClusterUtils(cluster, self.task_manager)
                    # self.cluster_util.reset_cluster()
                    master_services = cluster_util.get_services(
                        cluster.servers[:1], self.services_init, start_node=0)
                    if master_services is not None:
                        master_services = master_services[0].split(",")

                    self.quota = self._initialize_nodes(
                        self.task,
                        cluster,
                        self.disabled_consistent_view,
                        self.rebalanceIndexWaitingDisabled,
                        self.rebalanceIndexPausingDisabled,
                        self.maxParallelIndexers,
                        self.maxParallelReplicaIndexers,
                        self.port,
                        self.quota_percent,
                        services=master_services)

                    cluster_util.change_env_variables()
                    cluster_util.change_checkpoint_params()
                    self.log.info("{0} initialized".format(cluster))
            else:
                self.quota = ""

            # Enable dp_version since we need collections enabled
            if self.enable_dp:
                for server in self.cluster.servers:
                    shell_conn = RemoteMachineShellConnection(server)
                    cb_cli = CbCli(shell_conn)
                    cb_cli.enable_dp()
                    shell_conn.disconnect()
            # Enforce tls on nodes of all clusters
            if self.use_https and self.enforce_tls:
                for cluster in self.__cb_clusters:
                    for node in cluster.servers:
                        RestConnection(node).update_autofailover_settings(False, 120, False)
                        self.log.info("Setting cluster encryption level to strict on cluster "
                                      "with node {0}".format(node))
                        shell_conn = RemoteMachineShellConnection(node)
                        cb_cli = CbCli(shell_conn)
                        o = cb_cli.enable_n2n_encryption()
                        self.log.info(o)
                        shell_conn.disconnect()
                        RestConnection(node).set_encryption_level(level="strict")
                    self.log.info("Validating if services obey tls only on servers {0}".
                                  format(cluster.servers))
                    status = ClusterUtils(cluster, self.task_manager). \
                        check_if_services_obey_tls(cluster.servers)
                    if not status:
                        # ToDo: Make it fail once all services backport
                        self.log.error("Services did not honor enforce tls")

            for cluster in self.__cb_clusters:
                cluster_util = ClusterUtils(cluster, self.task_manager)
                if self.log_info:
                    cluster_util.change_log_info()
                if self.log_location:
                    cluster_util.change_log_location()
                if self.stat_info:
                    cluster_util.change_stat_info()
                if self.port_info:
                    cluster_util.change_port_info()
                if self.port:
                    self.port = str(self.port)

            self.__log_setup_status("finished")

            if not self.skip_init_check_cbserver:
                self.__log("started")
                self.sleep(5)
        except Exception, e:
            traceback.print_exc()
            self.task.shutdown(force=True)
            self.fail(e)

    def cleanup_pcaps(self):
        for server in self.servers:
            shell = RemoteMachineShellConnection(server)
            # Stop old instances of tcpdump if still running
            stop_tcp_cmd = "if [[ \"$(pgrep tcpdump)\" ]]; then kill -s TERM $(pgrep tcpdump); fi"
            o, e = shell.execute_command(stop_tcp_cmd)
            shell.execute_command("rm -rf pcaps")
            shell.execute_command("rm -rf " + server.ip + "_pcaps.zip")
            shell.disconnect()

    def start_collect_pcaps(self):
        for server in self.servers:
            shell = RemoteMachineShellConnection(server)
            # Create path for storing pcaps
            create_path = "mkdir -p pcaps"
            o, e = shell.execute_command(create_path)
            shell.log_command_output(o, e)
            # Install tcpdump command if it doesn't exist
            o, e = shell.execute_command("yum install -y tcpdump")
            shell.log_command_output(o, e)
            # Install screen command if it doesn't exist
            o, e = shell.execute_command("yum install -y screen")
            shell.log_command_output(o, e)
            # Execute the tcpdump command
            tcp_cmd = "screen -dmS test bash -c \"tcpdump -C 500 -w pcaps/pack-dump-file.pcap  -i eth0 -s 0 tcp\""
            o, e = shell.execute_command(tcp_cmd)
            shell.log_command_output(o, e)
            shell.disconnect()

    def start_fetch_pcaps(self):
        log_path = TestInputSingleton.input.param("logs_folder", "/tmp")
        for server in self.servers:
            remote_client = RemoteMachineShellConnection(server)
            # stop tcdump
            stop_tcp_cmd = "if [[ \"$(pgrep tcpdump)\" ]]; then kill -s TERM $(pgrep tcpdump); fi"
            o, e = remote_client.execute_command(stop_tcp_cmd)
            remote_client.log_command_output(o, e)
            # install zip unzip
            o, e = remote_client.execute_command("yum install -y zip unzip")
            remote_client.log_command_output(o, e)
            # zip the pcaps folder
            zip_cmd = "zip -r "+server.ip+"_pcaps.zip pcaps"
            o, e = remote_client.execute_command(zip_cmd)
            remote_client.log_command_output(o, e)
            # transfer the zip file
            zip_file_copied = remote_client.get_file(
                "/root",
                os.path.basename(server.ip+"_pcaps.zip"),
                log_path)
            self.log.info(
                "%s node pcap zip coped on client : %s"
                % (server.ip, zip_file_copied))
            if zip_file_copied:
                # clean up everything
                remote_client.execute_command("rm -rf pcaps")
                remote_client.execute_command("rm -rf "+server.ip+"_pcaps.zip")
                remote_client.disconnect()

    def tearDown(self):
        self.task_manager.shutdown_task_manager()
        self.task.shutdown(force=True)
        self.task_manager.abort_all_tasks()
        # Disable n2n encryption on nodes of all clusters
        if self.use_https and self.enforce_tls:
            for cluster in self.__cb_clusters:
                for node in cluster.servers:
                    CbServer.use_https = True
                    RestConnection(node).update_autofailover_settings(False, 120, False)
                    self.log.info("Setting cluster encryption level to control on cluster "
                                  "with node {0}".format(node))
                    shell_conn = RemoteMachineShellConnection(node)
                    cb_cli = CbCli(shell_conn)
                    _ = cb_cli.set_n2n_encryption_level(level="control")
                    _ = cb_cli.disable_n2n_encryption()
                    shell_conn.disconnect()
        CbServer.use_https = False
        if self.collect_pcaps:
            self.start_fetch_pcaps()
        self.log.info("Checking for core_dumps on servers")
        result, core_msg, stream_msg = self.check_coredump_exist(
            self.servers, force_collect=True)
        self.tearDownEverything()
        self.assertFalse(result, msg=core_msg + stream_msg)

    def tearDownEverything(self):
        if self.skip_setup_cleanup:
            return
        for cluster in self.__cb_clusters:
            cluster_util = ClusterUtils(cluster, self.task_manager)
            bucket_util = BucketUtils(cluster, cluster_util,
                                      self.task)
            try:
                if self.skip_buckets_handle:
                    return
                test_failed = (hasattr(self, '_resultForDoCleanups') and
                               len(self._resultForDoCleanups.failures or
                                   self._resultForDoCleanups.errors)) or \
                              (hasattr(self, '_exc_info') and \
                               self._exc_info()[1] is not None)

                if test_failed and TestInputSingleton.input.param("stop-on-failure", False) \
                        or self.input.param("skip_cleanup", False):
                    self.log.warn("CLEANUP WAS SKIPPED")
                else:
                    if test_failed:
                        # Collect logs because we have not shut things down
                        if TestInputSingleton.input.param("get-cbcollect-info",
                                                          False):
                            self.fetch_cb_collect_logs()

                        if TestInputSingleton.input.param('get_trace', None):
                            for server in cluster.servers:
                                try:
                                    shell = RemoteMachineShellConnection(server)
                                    output, _ = shell.execute_command("ps -aef|grep %s" %
                                                                      TestInputSingleton.input.param('get_trace', None))
                                    output = shell.execute_command("pstack %s" % output[0].split()[1].strip())
                                    self.infra_log.debug(output[0])
                                    shell.disconnect()
                                except:
                                    pass
                        else:
                            self.log.critical("Skipping get_trace !!")

                    rest = RestConnection(cluster.master)
                    alerts = rest.get_alerts()
                    if alerts is not None and len(alerts) != 0:
                        self.infra_log.warn("Alerts found: {0}".format(alerts))
                    self.log.debug("Cleaning up cluster")
                    cluster_util.cluster_cleanup(bucket_util)
            except BaseException as e:
                # kill memcached
                traceback.print_exc()
                self.log.warning("Killing memcached due to {0}".format(e))
                cluster_util.kill_memcached()
                # Increase case_number to retry tearDown in setup for next test
                self.case_number += 1000
            finally:
                if not self.input.param("skip_cleanup", False):
                    cluster_util.reset_cluster()
                # stop all existing task manager threads
                if self.cleanup:
                    self.cleanup = False
                else:
                    cluster_util.reset_env_variables()
        self.infra_log.info("========== tasks in thread pool ==========")
        self.task_manager.print_tasks_in_pool()
        self.infra_log.info("==========================================")
        if not self.tear_down_while_setup:
            self.task_manager.shutdown_task_manager()
            self.task.shutdown(force=True)

    def __log(self, status):
        try:
            msg = "{0}: {1} {2}" \
                .format(datetime.datetime.now(), self._testMethodName, status)
            RestConnection(self.servers[0]).log_client_error(msg)
        except:
            pass

    def __log_setup_status(self, status):
        msg = "========= basetestcase setup {0} for test #{1} {2} =========" \
            .format(status, self.case_number, self._testMethodName)
        self.log.info(msg)

    def _initialize_nodes(self, task, cluster, disabled_consistent_view=None,
                          rebalanceIndexWaitingDisabled=None,
                          rebalanceIndexPausingDisabled=None,
                          maxParallelIndexers=None,
                          maxParallelReplicaIndexers=None,
                          port=None, quota_percent=None, services=None):
        quota = 0
        init_tasks = []
        for server in cluster.servers:
            init_port = port or server.port or '8091'
            assigned_services = services
            if cluster.master != server:
                assigned_services = None
            init_tasks.append(
                task.async_init_node(
                    server, disabled_consistent_view,
                    rebalanceIndexWaitingDisabled,
                    rebalanceIndexPausingDisabled,
                    maxParallelIndexers,
                    maxParallelReplicaIndexers, init_port,
                    quota_percent, services=assigned_services,
                    index_quota_percent=self.index_quota_percent,
                    gsi_type=self.gsi_type))
        for _task in init_tasks:
            node_quota = self.task_manager.get_task_result(_task)
            if node_quota < quota or quota == 0:
                quota = node_quota
        if quota < 100 and not len(set([server.ip
                                        for server in self.servers])) == 1:
            self.log.warn("RAM quota was defined less than 100 MB:")
            for server in cluster.servers:
                remote_client = RemoteMachineShellConnection(server)
                ram = remote_client.extract_remote_info().ram
                self.log.debug("{0}: {1}".format(server.ip, ram))
                remote_client.disconnect()

        if self.jre_path:
            for server in cluster.servers:
                rest = RestConnection(server)
                rest.set_jre_path(self.jre_path)
        return quota

    def fetch_cb_collect_logs(self):
        log_path = TestInputSingleton.input.param("logs_folder", "/tmp")
        for node in self.servers:
            params = dict()
            if len(self.servers) != 1:
                params['nodes'] = 'ns_1@' + node.ip
            else:
                # In case of single node we have to pass ip as below
                params['nodes'] = 'ns_1@' + '127.0.0.1'

            self.log.info('Running cbcollect on node ' + node.ip)
            rest = RestConnection(node)
            status, _, _ = rest.perform_cb_collect(params)
            # Needed as it takes a few seconds before the collection start
            time.sleep(10)
            self.log.info("%s - cbcollect status: %s" % (node.ip, status))

            if status is True:
                self.log.info("Polling active_tasks to check cbcollect status")
                cb_collect_response = dict()
                retry = 0
                while retry < 30:
                    cb_collect_response = rest.ns_server_tasks(
                        "clusterLogsCollection")
                    self.log.debug("{}: CBCollectInfo Iteration {} - {}"
                                   .format(node.ip,
                                           retry,
                                           cb_collect_response["status"]))
                    if cb_collect_response['status'] == 'completed':
                        self.log.debug(cb_collect_response)
                        break
                    else:
                        # CB collect running, wait and check progress again
                        retry += 1
                        time.sleep(10)

                self.log.info("Copying cbcollect ZIP file to Client")
                remote_client = RemoteMachineShellConnection(node)
                cb_collect_path = \
                    cb_collect_response['perNode'][params['nodes']]['path']
                zip_file_copied = remote_client.get_file(
                    os.path.dirname(cb_collect_path),
                    os.path.basename(cb_collect_path),
                    log_path)
                self.log.info("%s node cb collect zip coped on client : %s"
                              % (node.ip, zip_file_copied))

                if zip_file_copied:
                    remote_client.execute_command("rm -f %s" % cb_collect_path)
                    remote_client.disconnect()
            else:
                self.log.error("API perform_cb_collect returned False")

    def sleep(self, timeout=15, message=None):
        self.log.debug("Sleep is called from %s -> %s():L%s"
                       % (inspect.stack()[1][1],
                          inspect.stack()[1][3],
                          inspect.stack()[1][2]))
        self.log.info("Reason: %s. Sleep for %s secs ..." % (message, timeout))
        time.sleep(timeout)

    def log_failure(self, message):
        self.log.error(message)
        self.summary.set_status("FAILED")
        if self.test_failure is None:
            self.test_failure = message

    def validate_test_failure(self):
        if self.test_failure is not None:
            self.fail(self.test_failure)

    def get_clusters(self):
        return self.__cb_clusters

    def get_task(self):
        return self.task

    def get_task_mgr(self):
        return self.task_manager

    def check_coredump_exist(self, servers, force_collect=False):
        bin_cb = "/opt/couchbase/bin/"
        lib_cb = "/opt/couchbase/var/lib/couchbase/"
        # crash_dir = "/opt/couchbase/var/lib/couchbase/"
        crash_dir_win = "c://CrashDumps"
        result = False
        dmpmsg = ""
        streammsg = ""

        def find_index_of(str_list, sub_str):
            for i in range(len(str_list)):
                if sub_str in str_list[i]:
                    return i
            return -1

        def get_gdb(shell_conn, dmp_path, dmp_name):
            dmp_file = dmp_path + dmp_name
            core_file = dmp_path + dmp_name.strip(".dmp") + ".core"
            shell_conn.execute_command("rm -rf " + core_file)
            shell_conn.execute_command("/" + bin_cb + "minidump-2-core "
                                       + dmp_file + " > " + core_file)
            gdb_out = shell_conn.execute_command("gdb --batch " + bin_cb
                                                 + "memcached -c " + core_file
                                                 + " -ex bt full -ex quit")[0]
            t_index = find_index_of(gdb_out, "Core was generated by")
            gdb_out = gdb_out[t_index:]
            gdb_out = " ".join(gdb_out)
            return gdb_out

        for server in servers:
            shell = RemoteMachineShellConnection(server)
            shell.extract_remote_info()
            self.log.debug(server.ip + " : Looking for crash dump files")
            crash_dir = lib_cb + "crash/"
            if shell.info.type.lower() == "windows":
                crash_dir = crash_dir_win
            dmp_files = shell.execute_command("ls -lt " + crash_dir)[0]
            dmp_files = [f for f in dmp_files if ".core" not in f]
            dmp_files = [f for f in dmp_files if "total" not in f]
            dmp_files = [f.split()[-1] for f in dmp_files if ".core" not in f]
            dmp_files = [f.strip("\n") for f in dmp_files]
            if dmp_files:
                msg = "Node %s - Core dump seen: %s" % (server.ip,
                                                        str(len(dmp_files)))
                dmpmsg += msg + "\n"
                self.log.error(msg)
                self.log.critical(server.ip + " : Stack Trace of first crash: "
                                  + dmp_files[-1])
                self.log.critical(get_gdb(shell, crash_dir, dmp_files[-1]))
                result = True
            else:
                self.log.debug(server.ip + ": No crash files found")

            self.log.debug(server.ip + ": Looking for CRITICAL messages")
            logs_dir = lib_cb + "logs/"
            log_files = shell.execute_command("ls " + logs_dir
                                              + "memcached.log.*")[0]
            for logFile in log_files:
                critical_msgs = shell.execute_command(
                    "grep -r 'CRITICAL' " + logFile.strip("\n")
                    + "| grep -v 'Rollback point not found'")[0]
                index = find_index_of(
                    critical_msgs,
                    "Fatal error encountered during exception handling")
                critical_msgs = critical_msgs[:index]
                if critical_msgs:
                    self.log.critical(server.ip + ": Found message in "
                                      + logFile.strip("\n"))
                    self.log.critical("".join(critical_msgs))
                    break
                streamreqfailed = "Stream request failed because " \
                                  "of the snap start seqno"
                found = shell.execute_command(
                    ("grep -r '{}' " + logFile.strip("\n"))
                    .format(streamreqfailed))[0]
                if found:
                    temp = "Found {} in {}".format(streamreqfailed, logFile)
                    self.log.error(temp)
                    streammsg += temp + "\n"
                    result = True
            shell.disconnect()
        if result and force_collect:
            self.fetch_cb_collect_logs()
            self.get_cbcollect_info = False

        return result, dmpmsg, streammsg
