class Marker:
    def __init__(self, marker_data):
        self.start = marker_data["Start time (ns)"]
        self.stop = marker_data["Stop time (ns)"]

    @staticmethod
    def from_dataset(dset):
        return Marker(dset.attrs)
