import streamlit as st
import pandas as pd
import re
import unicodedata
import phonenumbers
from icalendar import Calendar

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Gooli | Network Graph MVP", page_icon="🔵", layout="wide")

st.title("🔵 Gooli: Personal Network Cleaner")
st.markdown("""
**Drop your messy contact exports below.** We will clean, merge, and score your network using advanced entity resolution and interaction mining.
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
        parsed = phonenumbers.parse(str(phone_str), "IL") 
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except:
        pass
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
        
        if 'X-ABRELATEDNAMES' in vcard or 'mother' in vcard.lower() or 'brother' in vcard.lower():
            contact['Family'] = True
            
        contacts.append(contact)
    return contacts

# --- FILE UPLOADERS ---
st.subheader("1. The Base Network")
col1, col2, col3 = st.columns(3)

with col1:
    apple_file = st.file_uploader("🍏 Apple Contacts (.vcf)", type=['vcf'])
    with st.expander("How to get this file?"):
        st.markdown("""
        **From a Mac:**
        1. Open the **Contacts** app.
        2. Click on one contact, then press `Cmd + A` to select all.
        3. Go to top menu: **File > Export > Export vCard...**
        
        **From a PC (iCloud):**
        1. Go to [icloud.com/contacts](https://www.icloud.com/contacts/).
        2. Click the gear icon (bottom left) > **Select All**.
        3. Click the gear icon again > **Export vCard...**
        """)

with col2:
    google_file = st.file_uploader("🗂️ Google Contacts (.csv)", type=['csv'])
    with st.expander("How to get this file?"):
        st.markdown("""
        **From any browser:**
        1. Go to [contacts.google.com](https://contacts.google.com/).
        2. On the left sidebar, click the **Export** button.
        3. Choose **Google CSV** as the format.
        4. Click **Export**.
        """)

with col3:
    linkedin_file = st.file_uploader("💼 LinkedIn Connections (.csv)", type=['csv'])
    with st.expander("How to get this file?"):
        st.markdown("""
        **From LinkedIn:**
        1. Click your **Profile Picture (Me)** > **Settings & Privacy**.
        2. Go to **Data privacy** > **Get a copy of your data**.
        3. Select **"Want something in particular?"** and check the **Connections** box.
        4. Click **Request archive**. *(Takes ~10 mins to arrive).*
        """)

st.divider()

st.subheader("2. The Interaction Context (Optional)")
st.caption("Add these files to calculate who you actually interact with, boosting their relationship score.")

col4, col5 = st.columns(2)

with col4:
    calendar_file = st.file_uploader("📅 Google Calendar Export (.ics)", type=['ics'])
    with st.expander("How to get this file?"):
        st.markdown("""
        **From Google Calendar (Web):**
        1. Click the **Gear icon** (Settings) at the top right.
        2. On the left menu, click **Import & export**.
        3. Click the **Export** button.
        4. Unzip the downloaded file to find your `.ics` calendar file.
        """)

with col5:
    whatsapp_files = st.file_uploader("💬 WhatsApp Chat Exports (.txt)", type=['txt'], accept_multiple_files=True)
    with st.expander("How to get this file?"):
        st.markdown("""
        **From WhatsApp (Phone only):**
        1. Open a chat with a specific person.
        2. Tap their **name** at the top.
        3. Scroll to the bottom and tap **Export Chat**.
        4. Select **Without Media**.
        5. Save the `.txt` file to your computer.
        *(You can upload multiple .txt files at once!)*
        """)

st.divider()

# --- MAIN EXECUTION ---
if st.button("✨ Run Gooli Magic", type="primary"):
    if not any([apple_file, google_file, linkedin_file]):
        st.error("Please upload at least one Base Network file to begin.")
        st.stop()
        
    with st.spinner("Processing network graph and interaction data..."):
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
        
        df['First Name'] = df['First Name'].apply(lambda x: aggressive_clean(x, 'name'))
        df['Last Name'] = df['Last Name'].apply(lambda x: aggressive_clean(x, 'name'))
        df['Company'] = df['Company'].apply(lambda x: aggressive_clean(x, 'company'))
        df['Phone'] = df['Phone'].apply(normalize_phone)
        
        df['Full_Name'] = df['First Name'] + " " + df['Last Name']
        
        df['Source_Rank'] = df['Source'].map({'LinkedIn': 1, 'Apple': 2, 'Google': 3})
        df = df.sort_values('Source_Rank')
        
        merged_df = df.groupby(df['Full_Name'].replace("", float("NaN"))).agg({
            'First Name': 'first', 'Last Name': 'first',
            'Email': lambda x: next((i for i in x if i), ""),
            'Phone': lambda x: next((i for i in x if i), ""),
            'Company': lambda x: next((i for i in x if i), ""),
            'Job Title': lambda x: next((i for i in x if i), ""),
            'LinkedIn URL': lambda x: next((i for i in x if i), ""),
            'Family': 'max'
        }).reset_index(drop=True)
        
        merged_df = merged_df[(merged_df['First Name'] != "") | (merged_df['Last Name'] != "")]
        merged_df['Full_Name'] = merged_df['First Name'] + " " + merged_df['Last Name']

        # --- INTERACTION MINING ---
        interaction_scores = {}

        if calendar_file:
            cal = Calendar.from_ical(calendar_file.getvalue())
            for component in cal.walk('vevent'):
                attendees = component.get('attendee')
                if attendees:
                    if not isinstance(attendees, list): attendees = [attendees]
                    for attendee in attendees:
                        email = str(attendee).replace('MAILTO:', '').lower().strip()
                        if email:
                            interaction_scores[email] = interaction_scores.get(email, 0) + 5

        if whatsapp_files:
            for wa_file in whatsapp_files:
                content = wa_file.getvalue().decode('utf-8', errors='ignore')
                message_count = len(content.split('\n'))
                
                filename = wa_file.name.replace('WhatsApp Chat with ', '').replace('.txt', '').strip()
                clean_wa_name = aggressive_clean(filename, 'name')
                
                if message_count > 50:
                    interaction_scores[clean_wa_name] = 30 

        # --- RELATIONSHIP SCORING ---
        def calculate_score(row):
            score = 0
            if row['Email']: score += 15
            if row['Phone']: score += 15
            if row['LinkedIn URL']: score += 10
            if row['Company'] and row['Job Title']: score += 10
            
            bonus = 0
            if row['Email'] and row['Email'].lower() in interaction_scores:
                bonus += interaction_scores[row['Email'].lower()]
            if row['Full_Name'] and row['Full_Name'] in interaction_scores:
                bonus += interaction_scores[row['Full_Name']]
            
            score += min(bonus, 40)
            
            if row['Family']: score = 100 
            return min(score, 100)
            
        merged_df['Gooli_Score'] = merged_df.apply(calculate_score, axis=1)
        merged_df = merged_df.sort_values(by='Gooli_Score', ascending=False).reset_index(drop=True)

        # Clean up output display
        output_df = merged_df[['First Name', 'Last Name', 'Company', 'Job Title', 'Gooli_Score', 'Email', 'Phone', 'LinkedIn URL']]

        # --- OUTPUT ---
        st.success(f"✅ Magic Complete! Merged {len(df)} raw rows into {len(output_df)} clean entities.")
        
        st.subheader("Your Top Contacts")
        st.dataframe(output_df.head(100), use_container_width=True)
        
        csv = output_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Cleaned Network (.csv)",
            data=csv,
            file_name='Gooli_Cleaned_Network.csv',
            mime='text/csv',
            type="primary"
        )
