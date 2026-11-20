#   publish, subscribe, poll, ack (Acknowledgment), nack (Negative Acknowledgment), and the expiry reaper

class Broker:

    def __init__(self):
        self.subscribers = {}

    # register subscriber
    def subscribe(self, subscriber):

        for topic in subscriber.topics:

            if topic not in self.subscribers:
                self.subscribers[topic] = []

            self.subscribers[topic].append(subscriber)

    # publisher sends report
    def publish(self, report):

        print(f"\nPublishing: {report.description}")

        self.deliver(report)

    # topic routing
    def deliver(self, report):

        subscribers = self.subscribers.get(
            report.topic,
            []
        )

        for subscriber in subscribers:
            print(
                f"Delivered to {subscriber.name}"
            )

    # placeholders for integration
    def poll(self, subscriber):
        pass

    def ack(self, subscriber, report_id):
        print(
            f"ACK received from {subscriber.name}"
        )

    def nack(self, subscriber, report_id):
        print(
            f"NACK received from {subscriber.name}"
        )

    def expiry_reaper(self):
        pass