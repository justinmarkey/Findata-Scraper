## About

This repository is a simple way to download and store public earnings data from listed equities. Storage is in the from of JSON format.

## Installation Instructions

### 1. Clone the repository into target folder location
```bash
git clone https://github.com/justinmarkey/Findata-Scraper.git
```

### 2. Create and activate the environment
```bash
conda env create -f environment.yml
conda activate findata
```

### 3. Install the chromedriver for Selenium to work.
Install the appropriate chromedriver for your appropriate operating system

chromedriver link: https://googlechromelabs.github.io/chrome-for-testing/#stable

## Preview

Below is an example of earnings data JSON. See folder "exampledata" for an example.
![Info_Preview](./docs/earningsdata.png)

Similarly, below is an example of the "info" data JSON that is collected. This contains misc. data points about the companies. See folder "exampledata" for an example.
![Info_Preview](./docs/info.png)

Finally, below is an example of the "calendar" data JSON that is stored. This contains calendar events about the companies. Future plans for the project include  See folder "exampledata" for an example.
![Info_Preview](./docs/calendar.png)


## Troubleshooting
In certain cases, the XPATH location/identification for the download button on the Nasdaq website can break. The code is as robust as possible, but requires patching from time to time as Nasdaq makes html adjustments.
