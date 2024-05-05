class EnvNotFound(Exception):
    def __init__(self, notFoundEnv):
        self.message = f'[ERROR]: env variable for {notFoundEnv} not found in .env'
        super().__init__(self.message)
