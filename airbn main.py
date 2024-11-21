import requests
import json
from datetime import datetime, timedelta
import pandas as pd
from fake_useragent import UserAgent
from urllib.parse import urlparse
import base64
from apify import Actor
import logging

# Function to encode text to Base64
def encode_to_base64(text):
    text_bytes = text.encode("utf-8")
    encoded_text = base64.b64encode(text_bytes)
    encoded_text_str = encoded_text.decode("utf-8")
    return encoded_text_str

# Function to generate check-in and check-out dates
def generate_dates(check_in_date, num_days):
    check_in = datetime.strptime(check_in_date, '%Y-%m-%d')
    date_list = []
    for _ in range(num_days):
        check_out = check_in + timedelta(days=1)
        date_list.append((check_in.strftime('%Y-%m-%d'), check_out.strftime('%Y-%m-%d')))
        check_in += timedelta(days=1)
    return date_list

# Apify main function
async def main():
    await Actor.init()  # Initialize the Apify actor before any other operations

    input_data = await Actor.get_input()  # Get input from Apify
    links = input_data.get("startUrls")  # List of URLs
    check_in_date = input_data.get("check_in_date", "2024-11-21")  # Default to a given date
    num_days = input_data.get("numberOfDays", 10)  # Default number of days to generate
    check_out_date = input_data.get("checkOutDate", "2024-11-21")  # Default to a given date

    
    # check_in_check_out_dates = generate_dates(check_in_date, num_days)
    
    data_list = []
    ua = UserAgent()

    def get_value(data, path):
        keys = path.replace("[", ".").replace("]", "").split(".")
        for key in keys:
            if isinstance(data, list):
                key = int(key)
            try:
                data = data[key]
            except (KeyError, IndexError, TypeError):
                return None
        return data
    async def store_data_in_apify_dataset(data):
        try:
            await Actor.push_data(data)
            logging.info("Data pushed to Apify dataset successfully.")
        except Exception as e:
            logging.error(f"Error pushing data to Apify dataset: {e}")

    async def fetch_data(link, check_in_date, check_out_date):
        print(f"Processing link: {link} | Check-In: {check_in_date}, Check-Out: {check_out_date}")

        parsed_url = urlparse(link['url'])

        room_id = parsed_url.path.split('/')[-1]
        permanent = "StayListing"
        room_id = f"{permanent}:{room_id}"

        encoded_id = encode_to_base64(room_id)
        print(encoded_id)
        variables = {
            "id": encoded_id,
            "pdpSectionsRequest": {
                "adults": 2,
                "amenityFilters": None,
                "bypassTargetings": False,
                "children": 5,
                "checkIn": check_in_date,
                "checkOut": check_out_date,
                "pets": 0,
                "layouts": ["SIDEBAR", "SINGLE_COLUMN"],
                "sectionIds": [
                    "BOOK_IT_CALENDAR_SHEET", "CANCELLATION_POLICY_PICKER_MODAL",
                    "POLICIES_DEFAULT", "BOOK_IT_SIDEBAR", "URGENCY_COMMITMENT_SIDEBAR",
                    "BOOK_IT_NAV", "MESSAGE_BANNER", "HIGHLIGHTS_DEFAULT",
                    "BOOK_IT_FLOATING_FOOTER", "EDUCATION_FOOTER_BANNER",
                    "URGENCY_COMMITMENT", "EDUCATION_FOOTER_BANNER_MODAL"
                ]
            }
        }

        params = {
            'operationName': 'StaysPdpSections',
            'locale': 'en-GB',
            'currency': 'GB',
            'variables': json.dumps(variables),
            'extensions': '{"persistedQuery":{"version":1,"sha256Hash":"38218432c2d53194baa9c592ddd8e664cffcbcac58f0e118e8c1680eb9d58da7"}}'
        }

        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'user-agent': ua.random,
            'x-airbnb-api-key': 'd306zoyjsyarp7ifhu67rjxn52tv0t20',
            'x-csrf-without-token': '1',
            'x-requested-with': 'XMLHttpRequest'
        }

        try:
            url = 'https://www.airbnb.co.uk/api/v3/StaysPdpSections/38218432c2d53194baa9c592ddd8e664cffcbcac58f0e118e8c1680eb9d58da7'

            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()

            response_json = response.json()

            # Extract SEO Data
            seo_paths = {
                "Title": "data.presentation.stayProductDetailPage.sections.metadata.seoFeatures.title",
                "Meta Description": "data.presentation.stayProductDetailPage.sections.metadata.seoFeatures.metaDescription",
                "Canonical URL": "data.presentation.stayProductDetailPage.sections.metadata.seoFeatures.canonicalUrl",
                "Room Info": "data.presentation.stayProductDetailPage.sections.metadata.sharingConfig.title",
                "Property Type": "data.presentation.stayProductDetailPage.sections.metadata.sharingConfig.propertyType",
                "Room Rating": "data.presentation.stayProductDetailPage.sections.metadata.sharingConfig.starRating",  # e.g., 158 reviews

                "Total Reviews": "data.presentation.stayProductDetailPage.reviewCount",
                "Location": "data.presentation.stayProductDetailPage.sections.metadata.sharingConfig.location",
                "Capacity": "data.presentation.stayProductDetailPage.sections.metadata.sharingConfig.personCapacity",
                "Image URL": "data.presentation.stayProductDetailPage.sections.metadata.sharingConfig.imageUrl"
            }

            seo_data = {key: get_value(response_json, path) for key, path in seo_paths.items()}

            bar_price_data = response_json["data"]["presentation"]["stayProductDetailPage"]["sections"]["metadata"]["bookingPrefetchData"]["barPrice"]

            bar_price_details = {
                "Price Breakdown Title": get_value(bar_price_data, "explanationData.title"),
                "Price Breakdown Subtitle": get_value(bar_price_data, "explanationData.subtitle.legalDisclaimerSubtitle"),
                "Accessibility Label": bar_price_data.get("accessibilityLabel"),
                "Strike Through Price": get_value(bar_price_data, "displayPrices[0].priceString"),
                "Primary Price": get_value(bar_price_data, "displayPrices[1].priceString"),
                "Cleaning Fee": get_value(bar_price_data, "explanationData.priceGroups[0].items[1].priceString"),
                "Service Fee": get_value(bar_price_data, "explanationData.priceGroups[0].items[2].priceString"),
                "Taxes": get_value(bar_price_data, "explanationData.priceGroups[0].items[3].priceString"),
                "Total Price": get_value(bar_price_data, "explanationData.priceGroups[1].items[0].priceString"),
            }

            merged_data = {"Check-In Date": check_in_date, "Check-Out Date": check_out_date, **seo_data, **bar_price_details}

            # Store data in list for final output
            data_list.append(merged_data)

            print(f"Data fetched successfully for {link} | Check-In: {check_in_date}, Check-Out: {check_out_date}")

        except requests.RequestException as e:
            print(f"Request error for link {link} on date {check_in_date}: {e}")
        except KeyError as e:
            print(f"Key not found for link {link} on date {check_in_date}: {e}")
        except Exception as e:
            print(f"An error occurred for link {link} on date {check_in_date}: {e}")

    # Loop through links and fetch data
    for link in links:
        await fetch_data(link, check_in_date, check_out_date)

    # Convert list to DataFrame
    final_df = pd.DataFrame(data_list)

    # Sort DataFrame
    df_sorted = final_df.sort_values(by='Check-In Date')
    print(df_sorted)
    json_data = df_sorted.to_dict(orient="records")
                
                
    await store_data_in_apify_dataset(json_data)
    # Save the data to output (Apify expects JSON as output)
    # await Actor.set_output(df_sorted.to_json(orient="records"))

# Apify Actor initialization
if __name__ == '__main__':
    Actor.main(main)  # Run the main function
