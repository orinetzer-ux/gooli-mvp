import streamlit as st
import pandas as pd
import re
import unicodedata
import phonenumbers
import jellyfish

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Gooli | Network Graph MVP", page_icon="🔵", layout="wide")

st.title("🔵 Gooli: Personal Network Cleaner")
st.markdown("""
**Drop your messy contact exports below.** We will clean, merge, and score your network using advanced entity resolution.
*🔒 Privacy Guarantee: Your data is processed entirely in-memory and instantly deleted. Nothing is saved to a database.*
""")

# --- HELPER FUNCTIONS ---
def aggressive_clean(text, field_type="general"):
    if pd.isna(text) or text is None:
        return ""
    text = str(text).strip()
    text = unicodedata.normalize('NFKC', text)
    
    for char in ['\u200b', '\u200e', '\u200f', '\u202a', '\u202b', '\u202c', '\uFEFF']:
        text = text.replace(char, '')
        
    text = text.replace('', '')
    text = re.sub(r'\?{2,}', '', text) 
    
    if field_type == "name":
        text = re.sub(r'[^a-zA-Z\u0590-\u05FF \-\']', '', text)
    elif field_type == "company":
        text = text.replace('?', '')
        text = re.sub(r'[★_~🚀🇮🇱✔"|\[\]]+', '', text)

    return " ".join(text.split())

def normalize_phone(phone_str):
    if not phone_str or pd.isna(phone_str):
        return ""
    try:
        # Defaulting to IL (Israel) region if no country code is provided, you can change to US
        parsed = phonenumbers.parse(str(phone_str), "IL") 
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except:
        pass
    # Fallback: just strip non-digits
    digits = re.sub(r'\D', '', str(phone_str))
    return f"+{digits}" if digits else ""

def parse_vcf(file_bytes):
    content = file_bytes.decode('utf-8', errors='ignore')
    vcards = content.split('BEGIN:VCARD')
    contacts = []
    for vcard in vcards:
        if not vcard.strip(): continue
        contact = {'First Name': '', 'Last Name': '', 'Emails': [], 'Phones': [], 'Company': '', 'Title': '', 'Family': False}
        
        n_match = re.search(r'^N:(.*?);(.*?);', vcard, re.M)
        if n_match:
            contact['Last Name'] = n_match.group(1).strip()
            contact['First Name'] = n_match.group(2).strip()
            
        contact['Phones'] = [t.strip() for t in re.findall(r'^TEL.*?:(.*?)$', vcard, re.M)]
        contact['Emails'] = [e.strip() for e in re.findall(r'^EMAIL.*?:(.*?)$', vcard, re.M)]
        
        org = re.search(r'^ORG:(.*?)$', vcard, re.M)
        if org: contact['Company'] = org.group(1).strip()
        
        # Check for family tags (Apple specific)
        if 'X-ABRELATEDNAMES' in vcard or 'mother' in vcard.lower() or 'brother' in vcard.lower():
            contact['Family'] = True
            
        contacts.append(contact)
    return contacts

# --- FILE UPLOADERS ---
col1, col2, col3 = st.columns(3)
with col1:
    apple_file = st.file_uploader("🍏 Apple Contacts (.vcf)", type=['vcf'])
with col2:
    google_file = st.file_uploader("🗂️ Google Contacts (.csv)", type=['csv'])
with col3:
    linkedin_file = st.file_uploader("💼 LinkedIn Connections (.csv)", type=['csv'])

# --- MAIN EXECUTION ---
if st.button("✨ Run Gooli Magic", type="primary"):
    if not any([apple_file, google_file, linkedin_file]):
        st.error("Please upload at least one file to begin.")
        st.stop()
        
    with st.spinner("Processing network graph..."):
        all_contacts = []
        
        # 1. Parse Apple
        if apple_file:
            vcf_data = parse_vcf(apple_file.getvalue())
            for c in vcf_data:
                all_contacts.append({
                    'First Name': c['First Name'], 'Last Name': c['Last Name'],
                    'Email': c['Emails'][0] if c['Emails'] else "",
                    'Phone': c['Phones'][0] if c['Phones'] else "",
                    'Company': c['Company'], 'Job Title': c['Title'],
                    'LinkedIn URL': "", 'Family': c['Family'], 'Source': 'Apple'
                })
                
        # 2. Parse Google
        if google_file:
            gdf = pd.read_csv(google_file).fillna("")
            for _, row in gdf.iterrows():
                emails = [row[c] for c in gdf.columns if 'E-mail' in c and 'Value' in c and row[c]]
                phones = [row[c] for c in gdf.columns if 'Phone' in c and 'Value' in c and row[c]]
                all_contacts.append({
                    'First Name': row.get('Given Name', row.get('First Name', '')),
                    'Last Name': row.get('Family Name', row.get('Last Name', '')),
                    'Email': emails[0] if emails else "",
                    'Phone': phones[0] if phones else "",
                    'Company': row.get('Organization Name', ''),
                    'Job Title': row.get('Organization Title', ''),
                    'LinkedIn URL': "", 'Family': False, 'Source': 'Google'
                })
                
        # 3. Parse LinkedIn
        if linkedin_file:
            ldf = pd.read_csv(linkedin_file, skiprows=3).fillna("")
            for _, row in ldf.iterrows():
                all_contacts.append({
                    'First Name': row.get('First Name', ''), 'Last Name': row.get('Last Name', ''),
                    'Email': row.get('Email Address', ''), 'Phone': "",
                    'Company': row.get('Company', ''), 'Job Title': row.get('Position', ''),
                    'LinkedIn URL': row.get('URL', ''), 'Family': False, 'Source': 'LinkedIn'
                })

        # --- ENTITY RESOLUTION & CLEANING ---
        df = pd.DataFrame(all_contacts)
        
        # Apply Aggressive Cleaning
        df['First Name'] = df['First Name'].apply(lambda x: aggressive_clean(x, 'name'))
        df['Last Name'] = df['Last Name'].apply(lambda x: aggressive_clean(x, 'name'))
        df['Company'] = df['Company'].apply(lambda x: aggressive_clean(x, 'company'))
        df['Phone'] = df['Phone'].apply(normalize_phone)
        
        # Create a unified merge key (Email > Phone > Full Name)
        # For this MVP, we will group by Name + Company to catch duplicates
        df['Full_Name'] = df['First Name'] + " " + df['Last Name']
        
        # Sort so LinkedIn/Apple are prioritized for data retention over Google
        df['Source_Rank'] = df['Source'].map({'LinkedIn': 1, 'Apple': 2, 'Google': 3})
        df = df.sort_values('Source_Rank')
        
        # Grouping logic: Combine rows with the exact same Email, OR exact same Phone, OR exact same Name
        # To keep the Streamlit script fast, we aggregate by Name first. 
        # (A true graph DB does this better, but this works for a DataFrame MVP)
        merged_df = df.groupby(df['Full_Name'].replace("", float("NaN"))).agg({
            'First Name': 'first',
            'Last Name': 'first',
            'Email': lambda x: next((i for i in x if i), ""),
            'Phone': lambda x: next((i for i in x if i), ""),
            'Company': lambda x: next((i for i in x if i), ""),
            'Job Title': lambda x: next((i for i in x if i), ""),
            'LinkedIn URL': lambda x: next((i for i in x if i), ""),
            'Family': 'max' # If tagged true in any source, keep True
        }).reset_index(drop=True)
        
        # Drop rows with no name
        merged_df = merged_df[(merged_df['First Name'] != "") | (merged_df['Last Name'] != "")]

        # --- RELATIONSHIP SCORING ---
        def calculate_score(row):
            score = 0
            if row['Email']: score += 15
            if row['Phone']: score += 15
            if row['LinkedIn URL']: score += 10
            if row['Company'] and row['Job Title']: score += 10
            if row['Family']: score = 100 # Override for family
            return min(score, 100)
            
        merged_df['Gooli_Score'] = merged_df.apply(calculate_score, axis=1)
        
        # Sort by highest score
        merged_df = merged_df.sort_values(by='Gooli_Score', ascending=False).reset_index(drop=True)

        # --- OUTPUT ---
        st.success(f"✅ Magic Complete! Merged {len(df)} raw rows into {len(merged_df)} clean entities.")
        
        st.subheader("Your Top Contacts")
        st.dataframe(merged_df[['First Name', 'Last Name', 'Company', 'Job Title', 'Gooli_Score', 'Email', 'Phone']].head(100), use_container_width=True)
        
        # Download Button
        csv = merged_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Cleaned Network (.csv)",
            data=csv,
            file_name='Gooli_Cleaned_Network.csv',
            mime='text/csv',
            type="primary"
        )
