"""
Contains helper functions that can used across the module.
"""
import json
import logging
import os
import tempfile
from os.path import dirname

from jinja2 import Template

from ceph.ceph import CommandFailed
from ceph.utils import get_node_by_id, get_nodes_by_ids
from utility.utils import generate_self_signed_certificate

LOG = logging.getLogger(__name__)


class UnknownSpecFound(Exception):
    pass


class GenerateServiceSpec:
    """Creates the spec yaml file for deploying services and daemons using cephadm."""

    COMMON_SERVICES = [
        "mon",
        "mgr",
        "alertmanager",
        "crash",
        "grafana",
        "node-exporter",
        "prometheus",
    ]

    def __init__(self, node, cluster, specs):
        """
        Initialize the GenerateServiceSpec

        Args:
            node (CephNode): ceph node where spec file to be created
            cluster (Ceph.Ceph): ceph cluster (ceph-nodes)
            specs (Dict): service specifications

        Example::

            specs:
              - service_type: host
                address: true
                labels: apply-all-labels
                nodes:
                    - node2
                    - node3
              - service_type: mon
                placement:
                  nodes:
                    - node2
                    - node3
              - service_type: mgr
                placement:
                    count: 2
              - service_type: alertmanager
                placement:
                    count: 1
              - service_type: crash
                placement:
                    host_pattern: '*'
              - service_type: grafana
                placement:
                    count: 1
              - service_type: node-exporter
                placement:
                    host_pattern: '*'
              - service_type: prometheus
                placement:
                    count: 1
        """
        self.cluster = cluster
        self.node = node
        self.specs = specs
        self.template_path = dirname(__file__) + "/jinja_templates/"

    @staticmethod
    def get_hostname(node):
        """
        Returns Host Name of node

        Args:
            node (CephNode): node object

        Returns:
            hostname (Str)
        """
        return node.shortname

    @staticmethod
    def get_addr(node):
        """
        Returns IP Address of node

        Args:
            node (CephNode): node object

        Returns:
            IP Address (Str)
        """
        return node.ip_address

    @staticmethod
    def get_labels(node):
        """
        Returns role list of node

        Args:
            node (CephNode): node object

        Returns:
            node role list (List)
        """
        return node.role.role_list

    def get_hostnames(self, node_names):
        """
        Return list of hostnames

        Args:
            node_names (List): node names

        Returns:
            list of hostanmes (List)
        """
        nodes = get_nodes_by_ids(self.cluster, node_names)
        return [node.shortname for node in nodes]

    def _get_template(self, service_type):
        """
        Return Jinja template based on the service_type

        Args:
            service_type (Str): service name (ex., "host")

        Returns:
            template
        """
        path = self.template_path + f"{service_type}.jinja"
        with open(path) as fd:
            template = fd.read()
        return Template(template)

    def generate_host_spec(self, spec):
        """
        Return hosts spec content based on host config

        Args:
            spec (Dict): hosts specification

        Returns:
            hosts_spec (Str)

        Example::

            spec:
              - service_type: host
                address: true
                labels: apply-all-labels
                nodes:
                    - node2
                    - node3
        """
        template = self._get_template("host")
        hosts = []
        address = spec.get("address")
        labels = spec.get("labels")
        for node_name in spec["nodes"]:
            host = dict()
            node = get_node_by_id(self.cluster, node_name)
            host["hostname"] = self.get_hostname(node)
            if address:
                host["address"] = self.get_addr(node)
            if labels:
                host["labels"] = self.get_labels(node)
            hosts.append(host)

        return template.render(hosts=hosts)

    def generate_generic_spec(self, spec):
        """
        Return spec content for common services
        which is mentioned in COMMON_SERVICES::

             - mon
             - mgr
             - alertmanager
             - crash
             - grafana
             - node-exporter
             - prometheus

        Args:
            spec (Dict): common service spec config

        Returns:
            service_spec

        Example::

            spec:
              - service_type: mon
                unmanaged: boolean    # true or false
                placement:
                  count: 2
                  label: "mon"
                  host_pattern: "*"   # either hosts or host_pattern
                  nodes:
                    - node2
                    - node3
        """
        template = self._get_template("common_svc_template")
        node_names = spec["placement"].pop("nodes", None)
        if node_names:
            spec["placement"]["hosts"] = self.get_hostnames(node_names)

        return template.render(spec=spec)

    def generate_osd_spec(self, spec):
        """
        Return spec content for osd service

        Args:
            spec (Dict): osd service spec config

        Returns:
            service_spec (Str)

        Example::

            spec:
              - service_type: osd
                unmanaged: boolean    # true or false
                placement:
                  host_pattern: "*"   # either hosts or host_pattern
                  nodes:
                    - node2
                    - node3
                data_devices:
                    all: boolean      # true or false
                encrypted: boolean    # true or false

        """
        template = self._get_template("osd")
        node_names = spec["placement"].pop("nodes", None)
        if node_names:
            spec["placement"]["hosts"] = self.get_hostnames(node_names)

        return template.render(spec=spec)

    def generate_mds_spec(self, spec):
        """
        Return spec content for mds service

        Args:
            spec (Dict): mds service spec config

        Returns:
            service_spec (Str)

        Example::

            spec:
              - service_type: mds
                service_id: cephfs
                unmanaged: boolean    # true or false
                placement:
                  host_pattern: "*"   # either hosts or host_pattern
                  nodes:
                    - node2
                    - node3
                  label: mds

        :Note: make sure volume is already created.

        """
        template = self._get_template("mds")
        node_names = spec["placement"].pop("nodes", None)
        if node_names:
            spec["placement"]["hosts"] = self.get_hostnames(node_names)

        return template.render(spec=spec)

    def generate_nfs_spec(self, spec):
        """
        Return spec content for nfs service

        Args:
            spec (Dict): mds service spec config

        Returns:
            service_spec (Str)

        Example::

            spec:
              - service_type: nfs
                service_id: nfs-name
                unmanaged: boolean    # true or false
                placement:
                  host_pattern: "*"   # either hosts or host_pattern
                  nodes:
                    - node2
                    - node3
                  label: nfs
                spec:
                  pool: pool-name
                  namespace: namespace-name

        :Note: make sure pool is already created.
        """
        template = self._get_template("nfs")
        node_names = spec["placement"].pop("nodes", None)
        if node_names:
            spec["placement"]["hosts"] = self.get_hostnames(node_names)

        return template.render(spec=spec)

    def generate_rgw_spec(self, spec):
        """
        Return spec content for rgw service

        Args:
            spec (Dict): rgw service spec config

        Returns:
            service_spec (Str)

        Example::

            spec:
              - service_type: rgw
                service_id: my-rgw
                unmanaged: boolean    # true or false
                placement:
                  host_pattern: "*"   # either hosts or host_pattern
                  nodes:
                    - node2
                    - node3
                  label: rgw
                spec:
                  rgw_frontend_port: 8080
                  rgw_realm: east
                  rgw_zone: india
                  rgw_frontend_ssl_certificate: create-cert | <contents of crt>

            contents of rgw_spec.yaml file

                service_type: rgw
                service_id: rgw.india
                placement:
                  hosts:
                    - node5
                spec:
                  ssl: true
                  rgw_frontend_ssl_certificate: |
                    -----BEGIN PRIVATE KEY------
                    ...

        :Note: make sure realm, zone group and zone is already created.

        """
        template = self._get_template("rgw")
        node_names = spec["placement"].pop("nodes", None)
        if node_names:
            spec["placement"]["hosts"] = self.get_hostnames(node_names)

        # ToDo: This works for only one host. Not sure, how cephadm handles SSL
        #       certificate for multiple hosts.
        if spec["spec"].get("rgw_frontend_ssl_certificate") == "create-cert":
            subject = {"common_name": spec["placement"]["hosts"][0]}
            cert, key = generate_self_signed_certificate(subject=subject)
            pem = key + cert
            cert_value = "|\n" + pem
            spec["spec"]["rgw_frontend_ssl_certificate"] = "\n    ".join(
                cert_value.split("\n")
            )

            LOG.debug(pem)

            # Copy the certificate to all clients
            clients = self.cluster.get_nodes(role="client")

            # As the tests are executed on the hosts, copying the certs to them also
            rgws = self.cluster.get_nodes(role="rgw")
            nodes = clients + rgws

            for node in nodes:
                cert_file = node.remote_file(
                    sudo=True,
                    file_name=f"/etc/pki/ca-trust/source/anchors/{spec['service_id']}.crt",
                    file_mode="w",
                )
                cert_file.write(cert)
                cert_file.flush()

                node.exec_command(
                    sudo=True, cmd="update-ca-trust enable && update-ca-trust extract"
                )

        return template.render(spec=spec)

    def _get_render_method(self, service_type):
        """
        Return render definition based on service_type

        Args:
            service_type (Str): service name

        Returns:
            method (Func)
        """
        render_definitions = {
            "host": self.generate_host_spec,
            "osd": self.generate_osd_spec,
            "mds": self.generate_mds_spec,
            "nfs": self.generate_nfs_spec,
            "rgw": self.generate_rgw_spec,
        }

        try:
            if service_type in self.COMMON_SERVICES:
                return self.generate_generic_spec
            return render_definitions[service_type]
        except KeyError:
            raise NotImplementedError

    def create_spec_file(self):
        """
        Create spec file based on spec config and return file name

        Returns:
            temp_filename (Str)

        """
        spec_content = ""
        for spec in self.specs:
            method = self._get_render_method(spec["service_type"])
            if not method:
                raise UnknownSpecFound(f"unknown spec found - {spec}")
            spec_content += method(spec=spec)

        LOG.info(f"Spec yaml file content:\n{spec_content}")
        # Create spec yaml file
        temp_file = tempfile.NamedTemporaryFile(suffix=".yaml")
        spec_file = self.node.node.remote_file(
            sudo=True, file_name=temp_file.name, file_mode="w"
        )
        spec_file.write(spec_content)
        spec_file.flush()

        return temp_file.name


def get_cluster_state(cls, commands=[]):
    """
    fetch cluster state using commands provided along
    with the default set of commands::

        - ceph status
        - ceph orch ls -f json-pretty
        - ceph orch ps -f json-pretty
        - ceph health detail -f yaml

    Args:
        cls (CephAdmin): ceph.ceph_admin instance with shell access
        commands (List): list of commands

    """
    __CLUSTER_STATE_COMMANDS = [
        "ceph status",
        "ceph orch host ls",
        "ceph orch ls -f yaml",
        "ceph orch ps -f json-pretty",
        "ceph health detail -f yaml",
    ]

    __CLUSTER_STATE_COMMANDS.extend(commands)

    for cmd in __CLUSTER_STATE_COMMANDS:
        out, err = cls.shell(args=[cmd])
        LOG.info("STDOUT:\n %s" % out)
        LOG.error("STDERR:\n %s" % err)


def get_host_osd_map(cls):
    """
    Method to get the OSDs deployed in each of the hosts
    Args:
        cls: cephadm instance object

    Returns:
        Dictionary with host names as keys and osds deployed as value list
    """
    out, _ = cls.shell(args=["ceph", "osd", "tree", "-f", "json"])
    osd_obj = json.loads(out)
    osd_dict = {}
    for obj in osd_obj["nodes"]:
        if obj["type"] == "host":
            osd_dict[obj["name"]] = obj["children"]
    return osd_dict


def get_host_daemon_map(cls):
    """
    Method to get the daemons deployed in each of the hosts
    Args:
        cls: cephadm instance object

    Returns:
        Dictionary with host names as keys and names of the daemons deployed as value list
    """
    out, _ = cls.shell(args=["ceph", "orch", "ps", "-f", "json"])
    daemon_obj = json.loads(out)
    daemon_dict = dict()
    for daemon in daemon_obj:
        daemon_name = daemon["daemon_type"] + "." + daemon["daemon_id"]
        if daemon["hostname"] in daemon_dict.keys():
            daemon_dict[daemon["hostname"]].append(daemon_name)
        else:
            daemon_dict[daemon["hostname"]] = [daemon_name]
    return daemon_dict


def get_hosts_deployed(cls):
    """
    Method to get all the hosts deployed in the cluster
    Args:
        cls: cephadm instance object

    Returns:
        List of the names of hosts deployed in the cluster
    """
    out, _ = cls.shell(args=["ceph", "orch", "host", "ls", "-f", "json"])
    hosts = list()
    host_obj = json.loads(out)
    for host in host_obj:
        hosts.append(host["hostname"])
    return hosts


def file_or_path_exists(node, file_or_path):
    """
    Method to check abs path exists
    Args:
        node: node object where file should be exists
        file_or_path: ceph file or directory path

    Returns:
        boolean
    """
    try:
        out, _ = node.exec_command(cmd=f"ls -l {file_or_path}", sudo=True)
        LOG.info("Output : %s" % out.read().decode())
    except CommandFailed as err:
        LOG.error("Error: %s" % err)
        return False
    return True


def validate_log_file_after_enable(cls):
    """
    Method to verify generation of log files in default log directory when logging not enabled
    Args:
        cls: cephadm instance object

    Returns:
        boolean
    """
    out, _ = cls.shell(args=["ceph", "config", "set", "global", "log_to_file", "true"])
    out, _ = cls.shell(args=["ceph", "fsid"])
    fsid = out.strip()
    log_file_path = os.path.join("/var/log/ceph", fsid)
    daemon_dict = get_host_daemon_map(cls)
    roles_to_validate = ["mon", "mgr", "osd", "rgw", "mds"]

    daemon_valid = {
        k: [val for val in v if val.split(".")[0] in roles_to_validate]
        for (k, v) in daemon_dict.items()
    }

    for node in cls.cluster.get_nodes():
        try:
            if node.hostname not in daemon_valid.keys():
                continue
            daemons = daemon_valid[node.hostname]
            for daemon in daemons:
                file = os.path.join(log_file_path, f"ceph-{daemon}.log")
                if "rgw" in daemon:
                    file = os.path.join(log_file_path, f"ceph-client.{daemon}.log")
                LOG.info(
                    f"Verifying existence of log file {file} in host {node.hostname}"
                )
                fileExists = file_or_path_exists(node, file)
                if not fileExists:
                    LOG.error(
                        f"Log for {daemon} is not present in the node {node.ip_address}"
                    )
                    return False
            LOG.info(f"Log verification on node {node.ip_address} successful")
        except CommandFailed as err:
            LOG.error("Error: %s" % err)
            return False
    return True