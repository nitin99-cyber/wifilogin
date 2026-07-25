from login import login
from internet import is_connected
from network import is_cyberoam_network
def main():
    if is_connected():
        print("Internet is already connected")
        return
    if not is_cyberoam_network():
        print("Not connected to network")
        return
    print("Logging in")

    status, message =login()

    print(status)
    print(message)
if __name__ == "__main__":
    main()