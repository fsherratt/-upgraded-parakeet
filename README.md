# Project Upgraded Parakeet
[![Release Version](https://img.shields.io/badge/version-v0.2-blue)](https://github.com/fsherratt/upgraded-parakeet/releases)
[![GPLv3 license](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://choosealicense.com/licenses/lgpl-3.0/) [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Upgraded Parakeet is the next generation architecture for the [TeamBathDrones](https://www.teambathdrones.com) Research ERL entries. It focuses on robust highly decoupled nodes following the pub/sub model.

## Installation
See the setup [guide](docs/setup.md) for installation instructions

### Quick Installation
This requires vagrant.
Clone the repository and run
```
vagrant up
```

This should download the current VM snapshot, install the required packages and open a VM ready for work.

To close run
```
vagrant halt
```

To suspend run
```
vagrant suspend
```

To delete run
```
vagrant destroy
```



## Usage
The project follows the publish-subscriber model, with individual functions split into nodes and inter-process communication handled by the [Rabbit MQ](#) message broker

The [docs](/docs) folder contains detailed instructions of how each module works and interfacing to running modules

## Contributing
This repository is maintained by members of the University of Bath [TeamBathDrones](https://www.teambathdrones.com) research group.

If you find it useful and would like to give back pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
[GPLv3](https://choosealicense.com/licenses/gpl-3.0/s)
