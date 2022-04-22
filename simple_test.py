car_type = "SUV"
print("Outside all classes", car_type)
class Tesla:
    print("Type of the car within the Tesla class is:", car_type)

    def __init__(self, car_type):
        self.car_type = car_type

    def display_tesla(self):
        print("Type of car within a Tesla method:", car_type)

    # creating object to access method
    #


tsl_object = Tesla(car_type)

tsl_object.display_tesla()


class Lucid:
    print("Type of the car within the Lucid class is:", car_type)

    def __init__(self, car_type):
        self.car_type = car_type

    def display_lucid(self):
        print("Type of the car within the Lucid method:", car_type)


# creating an object to access the method within the Lucid Class.
lucid_object = Lucid(car_type)
lucid_object.display_lucid()