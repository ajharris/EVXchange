# dev_seed.py: Populate the dev database with sample users, cars, and stations
import os
from app import create_app, db
from models import User, Car, Station


def seed_dev_data(app):
    # Drop and recreate all tables
    db.drop_all()
    db.create_all()

    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@evxchange.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'supersecurepassword')
    admin = User(email=admin_email, name='Admin', is_verified=True, role='admin')
    # You may want to hash and store the password if your model supports it
    alice = User(email='alice.driver@example.com', name='Alice Driver', is_verified=True, role='user')
    bob = User(email='bob.owner@example.com', name='Bob Owner', is_verified=True, role='user')
    charlie = User(email='charlie.both@example.com', name='Charlie Both', is_verified=True, role='user')
    db.session.add_all([admin, alice, bob, charlie])
    db.session.commit()

    # Create cars for drivers
    car1 = Car(user_id=alice.id, make='Tesla', model='Model 3', year=2022, license_plate='ALC123')
    car2 = Car(user_id=charlie.id, make='Nissan', model='Leaf', year=2021, license_plate='CHR456')
    db.session.add_all([car1, car2])
    db.session.commit()

    # Create stations for owners
    station1 = Station(user_id=bob.id, name='Bob Station 1', address='123 Main St, City', latitude=37.7749, longitude=-122.4194, price_per_kwh=0.30)
    station2 = Station(user_id=bob.id, name='Bob Station 2', address='456 Oak Ave, City', latitude=37.7750, longitude=-122.4180, price_per_kwh=0.28)
    station3 = Station(user_id=charlie.id, name='Charlie Station', address='789 Pine Rd, City', latitude=37.7760, longitude=-122.4170, price_per_kwh=0.32)
    db.session.add_all([station1, station2, station3])
    db.session.commit()

    print('Sample dev data seeded!')
if __name__ == '__main__':
    # Use DATABASE_URL_DEV if set, else fallback to DATABASE_URL
    dev_db_url = os.environ.get('DATABASE_URL_DEV')
    app = create_app('development')
    if dev_db_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = dev_db_url
    with app.app_context():
        seed_dev_data(app)
