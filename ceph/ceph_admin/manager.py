"""
Module to deploy MGR service and individual daemon(s).

this module deploy MGR service and daemon(s) along with
handling other prerequisites needed for deployment.

"""
from ceph.ceph import ResourcesNotFoundError
from ceph.ceph_admin.apply import Apply
from ceph.ceph_admin.daemon_mixin import DaemonMixin
from ceph.utils import get_nodes_by_id


class ManagerRole(Apply, DaemonMixin):
    __ROLE = "mgr"

    def apply_mgr(self, **config):
        """
        Deploy MGR service using "orch apply" option
        Args:
            config: apply config arguments

        config:
            nodes: ['node1', node2']
        """
        cmd = Apply.apply_cmd + [self.__ROLE]
        nodes = get_nodes_by_id(self.cluster, config.get("nodes"))
        nodes = list(set(nodes + [self.installer.node]))

        if not nodes:
            raise ResourcesNotFoundError("Nodes not found: %s", config.get("nodes"))
        host_placement = [node.shortname for node in nodes]
        cmd.append("--placement '{}'".format(";".join(host_placement)))

        Apply.apply(
            self,
            role=self.__ROLE,
            command=cmd,
            placements=host_placement,
        )

    def daemon_add_mgr(self, **args):
        """
        Deploy MGR service using "orch apply" option
        Args:
            args: test arguments
        """
        raise NotImplementedError