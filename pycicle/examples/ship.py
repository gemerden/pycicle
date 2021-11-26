from pycicle import CmdParser, Argument


class Ship:
    def __init__(self, name):
        self.name = name
        self.x = 0
        self.y = 0
        self.sunk = False
        print(f"{self.name} was created")

    def move(self, dx, dy):
        if self.sunk:
            print(f"{self.name} is sunk, no more moves")
        self.x += dx
        self.y += dy
        print(f"{self.name} moved to {self.x}, {self.y}")

    def sink(self, do):
        self.sunk = do
        print(f"{self.name} sank")


class Move(CmdParser):
    dx = Argument(int)
    dy = Argument(int)


class Sink(CmdParser):
    sink = Argument(bool, default=True)


class ShipCommand(CmdParser):
    name = Argument(str)

    def __init__(self):
        super().__init__(self.create,
                         move=Move(self.move),
                         sink=Sink(self.sink))
        self.ship = None

    def create(self, name):
        self.ship = Ship(name)

    def move(self, dx, dy):
        self.ship.move(dx, dy)

    def sink(self, do):
        self.ship.sink(do)


if __name__ == '__main__':
    ship_command = ShipCommand()
    ship_command()
