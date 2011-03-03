class Environment(object):
    def __init__(self):
        pass
        #self.__dict__["pkgname"] = pkgname

class InternalFuncs(object):
    def __init__(self):
        self.env = Environment()
        self.libraries = []

    def import_script(self, script_path):
        exec compile(open(script_path).read(), "error", "exec") in self.env.__dict__
        
    def get(self, *libs):
        self.libraries = libs
