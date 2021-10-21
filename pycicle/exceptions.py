class ConfigError(ValueError):
    pass


class ValidationError(ValueError):
    def gui_message(self):
        before, _, after = str(self).partition(':')
        return after or before


