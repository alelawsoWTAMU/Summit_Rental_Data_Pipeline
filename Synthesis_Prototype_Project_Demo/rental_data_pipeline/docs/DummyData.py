import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Load original data to extract "real" equipment profiles
df_orig = pd.read_csv('master_ledger_all_weeks.csv')

# Create a master dictionary of unique equipment to ensure consistency
# We will define a "Unique Equipment" by its Equipment #
# and map it to its PO, SN Req, Description, and Monthly Rate.
equip_master = df_orig.drop_duplicates(subset=['EQUIPMENT #']).set_index('EQUIPMENT #')

# Get the target volume from Week 17 (~635 lines)
target_vol = len(df_orig[df_orig['WK #'] == 17])

# To keep the monthly spend at ~$2.5M with 635 lines, we need to scale the rates
# Original total monthly cost was likely higher per item, so we scale the master rates
target_avg_rate = 2500000 / (target_vol * 4.33)
actual_avg_rate = equip_master['MO. RATE $'].replace('[\$, ]', '', regex=True).replace('—', '0').astype(float).mean()
rate_scaler = target_avg_rate / actual_avg_rate if actual_avg_rate > 0 else 1

def get_random_date_in_week(year, week):
    first_day_of_year = datetime(year, 1, 1)
    start_of_week = first_day_of_year + timedelta(days=(week - 1) * 7 - first_day_of_year.weekday())
    return start_of_week + timedelta(days=np.random.randint(0, 7))

# We need a pool of Equipment IDs to pull from to ensure they "persist" across weeks
available_equip_ids = equip_master.index.tolist()

final_rows = []

for week in range(1, 16):
    # Determine how many lines this week (with variance)
    current_wk_count = int(np.random.normal(target_vol, target_vol * 0.03))
    
    # Pick equipment for this week. Pulling from the master list ensures PO/Req#/Desc stay locked to the ID.
    selected_ids = np.random.choice(available_equip_ids, size=current_wk_count, replace=True)
    
    for eid in selected_ids:
        profile = equip_master.loc[eid]
        
        # Consistent Data Points from Master
        po_num = profile['PO #']
        req_num = profile['SN REQ #']
        desc = profile['DESCRIPTION']
        rental_co = profile['RENTAL CO.']
        equip_type = profile['TYPE OF EQUIP.']
        pub_by = profile['PUBLISHED BY']
        
        # Cost Logic: Scaled for volume but consistent for that ID
        orig_rate = str(profile['MO. RATE $']).replace('$', '').replace(',', '').replace(' ', '').replace('—', '0')
        scaled_rate = float(orig_rate) * rate_scaler
        
        start_date = get_random_date_in_week(2026, week)
        # End dates stay within a realistic range but linked to the "equipment type" logic
        end_date = start_date + timedelta(days=np.random.randint(30, 180))
        
        final_rows.append({
            'YEAR': 2026,
            'WK #': week,
            'RENTAL CO.': rental_co,
            'TYPE OF EQUIP.': equip_type,
            'EQUIPMENT #': eid,
            'DESCRIPTION': desc,
            'RENT START': start_date.strftime('%m/%d/%Y'),
            'PROJ. END': end_date.strftime('%m/%d/%Y'),
            'PO #': po_num,
            'SN REQ #': req_num,
            'MO. RATE $': f"${scaled_rate:,.2f} ",
            'COMMENTS': 'Linked Profile Entry',
            'PUBLISHED BY': pub_by
        })

df_v4 = pd.DataFrame(final_rows)
df_16_17 = df_orig[df_orig['WK #'].isin([16, 17])].copy()

# Final assembly
master_ledger_v4 = pd.concat([df_v4, df_16_17], ignore_index=True)
master_ledger_v4 = master_ledger_v4.sort_values(by=['WK #'], ascending=True)

master_ledger_v4.to_csv('master_ledger_linked_v4.csv', index=False)

# Verification check: Check if one equipment ID has the same PO across multiple weeks
sample_id = master_ledger_v4['EQUIPMENT #'].iloc[0]
verification = master_ledger_v4[master_ledger_v4['EQUIPMENT #'] == sample_id][['WK #', 'EQUIPMENT #', 'PO #', 'MO. RATE $']]
print(verification.head())

# Save the updated persistent logic script
code_v4 = """import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Logic: Ensures Equipment ID is the primary key. 
# PO, Req #, and Description are locked to that ID across all weeks.

df_orig = pd.read_csv('master_ledger_all_weeks.csv')
equip_master = df_orig.drop_duplicates(subset=['EQUIPMENT #']).set_index('EQUIPMENT #')

# Scaling rates to support ~640 lines while keeping monthly spend at ~$2.5M
target_vol = 635
target_avg_rate = 2500000 / (target_vol * 4.33)
actual_avg_rate = equip_master['MO. RATE $'].replace('[\\\\$, ]', '', regex=True).replace('—', '0').astype(float).mean()
rate_scaler = target_avg_rate / actual_avg_rate

rows = []
for week in range(1, 16):
    count = int(np.random.normal(target_vol, target_vol * 0.03))
    ids = np.random.choice(equip_master.index.tolist(), size=count, replace=True)
    
    for eid in ids:
        p = equip_master.loc[eid]
        rate = float(str(p['MO. RATE $']).replace('$','').replace(',','').replace('—','0')) * rate_scaler
        start = datetime(2026, 1, 1) + timedelta(weeks=week-1, days=np.random.randint(0,7))
        
        rows.append({
            'YEAR': 2026, 'WK #': week, 'RENTAL CO.': p['RENTAL CO.'], 
            'TYPE OF EQUIP.': p['TYPE OF EQUIP.'], 'EQUIPMENT #': eid,
            'DESCRIPTION': p['DESCRIPTION'], 'RENT START': start.strftime('%m/%d/%Y'),
            'PROJ. END': (start + timedelta(days=120)).strftime('%m/%d/%Y'),
            'PO #': p['PO #'], 'SN REQ #': p['SN REQ #'],
            'MO. RATE $': f"${rate:,.2f} ", 'COMMENTS': 'Persistent Profile',
            'PUBLISHED BY': p['PUBLISHED BY']
        })

df_final = pd.concat([pd.DataFrame(rows), df_orig[df_orig['WK #'].isin([16, 17])]], ignore_index=True)
df_final.to_csv('master_ledger_linked_v4.csv', index=False)
"""
with open('generate_linked_ledger_v4.py', 'w') as f:
    f.write(code_v4)