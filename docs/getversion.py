def define_env(env):
        
    @env.macro
    def flowpaths_version_pyproject():
        # This function reads the .toml file pyproject.toml to get the version of the package
        try:
            lines = open("pyproject.toml").readlines()
            for line in lines:
                if "version" in line:
                    return line.split("=")[1].strip().replace('"', '')
            return "0.1.0"
        except:
            return "0.1.0"