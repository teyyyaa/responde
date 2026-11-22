"""

from examples.demo_full import main


if __name__ == "__main__":
    main()
ROLE:
API, Integration, and Testing

FOLDERS & FILES RESPONSIBLE FOR:
broker/
└── api.py
examples/
tests/
main.py

OBJECTIVE: Combine all components into one complete system.
- Integration
    - Connect Publisher → Broker.
    - Connect Broker → Subscribers.
    - Connect Queue → Database.
- API Development
    - Create endpoints:
        - POST /publish
        - POST /subscribe
        - POST /respond
        - GET /reports
- Testing
    - Create:
        - test_routing.py
        - test_redelivery.py
        - test_delivery.py
- Test:
    - Topic filtering
    - Queue persistence
    - Redelivery
    - Response status updates

"""