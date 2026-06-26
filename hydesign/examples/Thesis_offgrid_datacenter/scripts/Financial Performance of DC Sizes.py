# -*- coding: utf-8 -*-
"""
Calculates the financial performance of optimal workload mixes across varying data center sizes.

Reads all parameter sweep results (Feasible_3D_Sweep_Results_99.9pct_IT*.csv), 
filters for configurations where the firm load (Tier A) is at least 8 MW, and applies 
the master thesis macroeconomic calculation engine. Calculates Gross Revenue, Fixed Costs 
(via Capital Recovery Factor), and Variable Costs (Water + Electricity PPA) to identify 
the Annualized Net Profit for the economically optimal configuration at each capacity.
"""

import pandas as pd
import glob
import os
import re
import numpy as np

# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================
def calculate_crf(rate, years):
    """Calculates the Capital Recovery Factor."""
    if rate == 0: return 1 / years
    return (rate * (1 + rate)**years) / ((1 + rate)**years - 1)

def extract_economic_results():
    """Main execution function to extract data and compute economic outcomes."""
    
    # --- DYNAMIC PATH RESOLUTION ---
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    
    thesis_dir = os.path.abspath(os.path.join(scripts_dir, '..'))
    
    results_dir = os.path.join(thesis_dir, "results")
    
    file_pattern = os.path.join(results_dir, 'Feasible_3D_Sweep_Results_99.9pct_IT*.csv')
    files = glob.glob(file_pattern)

    if not files:
        print(f"[WARNING] No files found matching the pattern in:\n{results_dir}")
        return

    # --- Financial Inputs ---
    REVENUE_PER_MWH = {"A": 4000.0, "B1": 2800.0, "B2": 1600.0, "C": 400.0} 
    OTHER_VARIABLE_OPEX_EUR_PER_MWH = 3  
    DISCOUNT_RATE = 0.075                
    FACILITY_CAPEX_PER_MW = 9.60         
    FACILITY_LIFETIME = 20               
    IT_CAPACITIES_PER_MW = 15.33         
    IT_LIFETIME = 5                      
    FIXED_OPEX_PER_MW = 0.25             

    ann_fixed_per_mw = (FACILITY_CAPEX_PER_MW * calculate_crf(DISCOUNT_RATE, FACILITY_LIFETIME)) + \
                       (IT_CAPACITIES_PER_MW * calculate_crf(DISCOUNT_RATE, IT_LIFETIME)) + \
                       FIXED_OPEX_PER_MW

    results = []

    for file in files:
        filename = os.path.basename(file)
        match = re.search(r'Feasible_3D_Sweep_Results_99\.9pct_IT([\d\.]+)\.csv', filename)
        if not match: continue
        capacity_mw = float(match.group(1))

        try:
            df = pd.read_csv(file)
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            continue

        if df.empty: continue

        filtered_df = df[df['Tier_A_MW'] >= 8].copy()
        if filtered_df.empty:
            continue

        e_comm = filtered_df['Energy_A_Annual_GWh'] + filtered_df['Energy_B1_Annual_GWh'] + filtered_df['Energy_B2_Annual_GWh']
        e_c = np.maximum(0, filtered_df['Total_Delivered_Annual_GWh'] - e_comm)
        
        filtered_df['Gross_Rev_EUR'] = (
            filtered_df['Energy_A_Annual_GWh'] * REVENUE_PER_MWH["A"] +
            filtered_df['Energy_B1_Annual_GWh'] * REVENUE_PER_MWH["B1"] +
            filtered_df['Energy_B2_Annual_GWh'] * REVENUE_PER_MWH["B2"] +
            e_c * REVENUE_PER_MWH["C"]
        ) * 1000

        filtered_df['Water_OPEX_EUR'] = OTHER_VARIABLE_OPEX_EUR_PER_MWH * (filtered_df['Total_Delivered_Annual_GWh'] * 1000)
        total_fixed_costs_m = ann_fixed_per_mw * capacity_mw

        filtered_df['Elec_Cost_M'] = (filtered_df['Total_Delivered_Annual_GWh'] * 1000 * filtered_df['LCOE_delivered']) / 1e6
        filtered_df['Net_Profit_M'] = (filtered_df['Gross_Rev_EUR'] - filtered_df['Water_OPEX_EUR']) / 1e6 - filtered_df['Elec_Cost_M'] - total_fixed_costs_m

        best_row = filtered_df.loc[filtered_df['Net_Profit_M'].idxmax()]

        results.append({
            'IT (MW)': capacity_mw,
            'Mix (A/B1/B2)': f"{int(best_row['Tier_A_MW'])}/{int(best_row['Tier_B1_MW'])}/{int(best_row['Tier_B2_MW'])}",
            'Delivered (GWh)': round(best_row['Total_Delivered_Annual_GWh'], 1),
            'Gross Rev (€M)': round(best_row['Gross_Rev_EUR'] / 1e6, 2),
            'Fixed Cost (€M)': round(total_fixed_costs_m, 2),
            'Elec Cost (€M)': round(best_row['Elec_Cost_M'], 2),
            'Net Profit (€M)': round(best_row['Net_Profit_M'], 2)
        })

    results_df = pd.DataFrame(results)
    if results_df.empty:
        print("No valid data could be processed.")
        return

    results_df = results_df.sort_values(by='IT (MW)').reset_index(drop=True)

    print("Data Center Master Economic Overview")
    print(results_df.to_string(index=False))

if __name__ == "__main__":
    extract_economic_results()