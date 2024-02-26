import pandas as pd

# Load the datasets from CSV files
md_online_df = pd.read_csv('./csv_manipulation/MD-Online.csv')
change_healthcare_df = pd.read_csv('./csv_manipulation/Change-Healthcare.csv')

# Merging dataframes on PayorID to find common entries
common_payors = pd.merge(md_online_df, change_healthcare_df, on='PayorID', suffixes=('_MDOnline', '_ChangeHealthcare'))

# To display the common payors, you can use:
print(common_payors[['Payer Name_MDOnline', 'PayorID', 'Payer Name_ChangeHealthcare']].head())

# If you want to save this to a CSV file for easier review:
common_payors[['Payer Name_MDOnline', 'PayorID', 'Payer Name_ChangeHealthcare']].to_csv('common_payors.csv', index=False)