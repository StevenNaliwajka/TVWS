from Codebase.FileIO.load_hackrf_iq import load_hackrf_iq

from Codebase.Filter.filter_singal import filter_singal
from Codebase.MetaData.metadata_object import MetaDataObj

def run():
    metadata = MetaDataObj()
    iq = load_hackrf_iq(metadata.wired_iq_file_path)

    filter_singal(metadata, iq)


if __name__ == "__main__":
    run()
