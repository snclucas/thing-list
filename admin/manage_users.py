import argparse

from database_functions import add_user


parser = argparse.ArgumentParser(description='ThingList: manage users.')
# Add an argument
parser.add_argument('--username', type=str, required=True)
parser.add_argument('--email', type=str, required=True)
parser.add_argument('--password', type=str, required=True)

args = parser.parse_args()
print('Adding user:', args.username)

add_user(username=args.username, email=args.email, password=args.password)
