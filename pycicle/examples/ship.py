from pycicle import CmdParser, Argument


class Ship:
    def __init__(self, name):
        self.name = name
        self.x = 0
        self.y = 0
        self.sunk = False
        print(f"'{self.name}' was created")

    def move(self, dx, dy):
        if self.sunk:
            print(f"'{self.name}' sank, no more moving around")
        else:
            self.x += dx
            self.y += dy
            print(f"'{self.name}' moved to ({self.x}, {self.y})")

    def sink(self, sunk):
        self.sunk = sunk
        print(f"'{self.name}' {'sank' if sunk else 'unsank'}")

    def __str__(self):
        if self.sunk:
            return f"'{self.name}' sunk at ({self.x}, {self.y})"
        return f"'{self.name}' at ({self.x}, {self.y})"


class Move(CmdParser):
    dx = Argument(int)
    dy = Argument(int)


class Sink(CmdParser):
    sunk = Argument(bool, default=True)


def stop():
    raise KeyboardInterrupt


class ShipCommand(CmdParser):
    name = Argument(str)

    def __init__(self):
        super().__init__(self.create,
                         move=Move(self.move),
                         sink=Sink(self.sink),
                         quit=CmdParser.from_callable(stop))
        self.ship = None

    def create(self, name):
        self.ship = Ship(name)

    def move(self, dx, dy):
        self.ship.move(dx, dy)

    def sink(self, sunk):
        self.ship.sink(sunk)


if __name__ == '__main__':
    ship_command = ShipCommand()
    ship_command.prompt()
