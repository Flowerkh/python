"""
Please complete the following API based on requirements.

You will get the data from "price.csv" and "portfolio.csv" in order to save data we have to design Stock class
  The class should have name share price as property.
  Also, it will have methodn sell and  cost method for the fucture.

  1. Read data :
                def read_portfolio(filename):
                def read_prices(filename):
  2. Report data:
                def make_report_data(portfolio, prices):
                def print_report(reportdata):
                def portfolio_report(portfoliofile, pricefile):

In order to complete requirements, you should make your own packages:

1) Stock.py
2) Report.py
3) pcost.py

The usage will be like below procedure:

    read data from price.csv portfolio.csv
    + portfolio.csv : it contains name shares and price (the unit price which is the cost at the time when I bought)
    + price.csv : it contains the current stock price

    make data structure through stock classs

    then hold the portfolio information and compute the total cost and update status of my portfolio

After complete each API then you will get report as like following.
You should be able to run your functions the same as before:
however, you should run this function in python interpreter.

python
>>> import pcost
>>> pcost.portfolio_cost('portfolio.csv')
44671.15
>>> import report
>>> report.portfolio_report('portfolio.csv', 'prices.csv')
      Name     Shares      Price     Change
---------- ---------- ---------- ----------
        AA        100       9.22     -22.98
       IBM         50     106.28      15.18
       CAT        150      35.46     -47.98
      MSFT        200      20.89     -30.34
        GE         95      13.48     -26.89
      MSFT         50      20.89     -44.21
       IBM        100     106.28      35.84
>>>
"""

import fileparse
from stock import Stock


def read_portfolio(filename):
    '''
    Read a stock portfolio file into a list of dictionaries with keys
    name, shares, and price.

    When reads portfolio you should make stock class.
    The class should have name share price as property.
    Also, it will have methodn sell and  cost method
    '''


def read_prices(filename):
    '''
    Read a CSV file of price data into a dict mapping names to prices.
    '''
    with open(filename) as lines:
        return dict(fileparse.parse_csv(lines, types=[str, float], has_headers=False))


def make_report_data(portfolio, prices):
    '''
    Make a list of (name, shares, price, change) tuples given a portfolio list
    and prices dictionary.
    '''
    return rows


def print_report(reportdata):
    '''
    Print a nicely formated table from a list of (name, shares, price, change) tuples.
    '''


def portfolio_report(portfoliofile, pricefile):
    '''
    Make a stock report given portfolio and price data files.
    '''


def main(args):
    if len(args) != 3:
        raise SystemExit('Usage: %s portfile pricefile' % args[0])
    portfolio_report(args[1], args[2])


if __name__ == '__main__':
    import sys

    main(sys.argv)