from cdm.store.index_manager import IndexManager


class FakeIndices:
    def __init__(self):
        self.created = []
        self.aliases = []

    def exists(self, index):
        return False

    def create(self, index, body):
        self.created.append((index, body))

    def put_alias(self, index, name):
        self.aliases.append((index, name))


class FakeClient:
    def __init__(self):
        self.indices = FakeIndices()


def test_create_adds_write_alias_for_logical_index():
    client = FakeClient()

    IndexManager(client).create("legislation")

    assert client.indices.created[0][0] == "congress-legislation"
    assert client.indices.aliases == [
        ("congress-legislation", "congress-legislation-write")
    ]