from lpms import out
from lpms import constants as cst

class SyncronizeRepo(object):
    def __init__(self):
        self.data = None
        self.remote = None
        self._type = None

    def read_conf_file(self):
        with open(cst.repo_conf) as data:
            self.data = data.read().split("\n")

    def run(self, repo):
        keyword = "["+repo+"]"

        # import repo.conf
        self.read_conf_file()
        
        if keyword in self.data:
            first = self.data.index(keyword)
            for line in self.data[first+1:]:
                if line.startswith("["):
                    continue
                if self._type is None and line.startswith("type"):
                    self._type = line.split("@")[1].strip()
                elif self.remote is None and line.startswith("remote"):
                    self.remote = line.split("@")[1].strip()

        if self._type == "git":
            from lpms.syncers import git as syncer


        out.notify("synchronizing %s from %s" % (out.color(repo, "green"), self.remote))

        syncer.run(repo, self.remote)
