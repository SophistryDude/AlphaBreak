# Securities_prediction_model

Projected goal:
Create an application that sends push notifications // daily reports for securities that have a high likelyhood of being a good short term trade. 

Step 1 - Creating a target:
  Define a trendline break-
    SP_historical_data line #348
  Define trendline break accuracy -
    SP_historical_data line #381
Step 2 - Implementing technical indicators:
  Definition of technical indicators-
    SP_Historical_data line #26
  Define technical indicators-
    SP_Historical_data line #89
  Assess each technical indicator using trendline break acc function (on 1 historical security)-
    SP_Historical_data_line #457
Step 3 - Create model for accuracy testing and refinement
  RFC model - 
    SP_Historical_data_line #515
  Keras model - 
    SP_Historical_data_line #528
  Reproduce Step 3 for larger training set (eg S&P historical data for the past 35 years)
  Test more models, refine model, increase accuracy metrics, fine tune model
Step 4 - Black-Scholes fair value comparision for stock options
  Black-Scholes function-
    SP_Historical_data_line #606
  Create model for fair price-
    SP_Historical_data_line #660
Step 5 - LSTM to predict trend line break
  SP_Historical_data_line #801
  Train model, increase relu nodes based on computing power available, increase sample size of historical securities data, improve accuracy, Develop additional models for 5m,10m, 30m, 1hr, 2hr, 1day, 5day, weekly etc charts
Step 6 - Create database to hold data
Step 7 - Create Airflow service
Step 8 - Visualizations
Step 9 - Application & delivery
Step 10 - pricing model & monetization
Step 11 - Additioanal features
  Securities watch list
  Report on which companies are being held by hedge funds
  Forex trading application -
    Create models that calculate what the impact on currency evaluation multiple factors removed
  
  
