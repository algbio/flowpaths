def define_env(env):

    @env.macro
    def flowpaths_version():
        try:
            lines = open("VERSION").readlines()
            version = lines[0].strip()
            return version
        except:
            return "0.1.0"