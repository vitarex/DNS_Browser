import json

class QueueEvent():
    def __init__(self, data=None, event=None, id=None, retry=None):
        if all(p is None for p in [data, event, id, retry]):
            raise ValueError("At least one of data, event, id, or rertry must have a value.")
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry

    def message(self):
        messageList = []
        if self.data:
            messageList.append("data: {}".format(self.data))
        if self.event:
            messageList.append("event: {}".format(self.event))
        if self.id:
            messageList.append("id: {}".format(self.id))
        if self.retry:
            messageList.append("retry: {}".format(self.retry))
        return "\n".join(messageList) + "\n\n"
