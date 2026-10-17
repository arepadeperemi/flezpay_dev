import random

class CustomLogisticsAPI:
    """
    Placeholder client for a Custom Logistics (e.g. FedEx, DHL, or internal proxy).
    This handles deliveries outside of Nigeria where Kxpress is not supported.
    """
    
    def calculate_shipping(self, from_state, from_lga, to_state, to_lga, weight):
        """
        Dummy calculation returning a placeholder shipping fee.
        """
        # Random placeholder fee for international/custom delivery
        placeholder_fee = 5000.0 * max(1.0, float(weight))
        return {
            "status": True, 
            "data": {
                "totalAmount": placeholder_fee,
                "message": "Custom Logistics Estimated Price"
            }
        }

    def generate_waybill(self, payload):
        """
        Dummy waybill generation.
        Returns a mock tracking number.
        """
        tracking_no = f"CUSTOM-INTL-{random.randint(100000, 999999)}"
        return {
            "status": True,
            "data": {
                "waybill_no": tracking_no,
                "message": "Custom Logistics waybill successfully created."
            }
        }

    def get_states(self):
        counties = [
            {"id": "ke_01", "name": "Mombasa"},
            {"id": "ke_02", "name": "Kwale"},
            {"id": "ke_03", "name": "Kilifi"},
            {"id": "ke_04", "name": "Tana River"},
            {"id": "ke_05", "name": "Lamu"},
            {"id": "ke_06", "name": "Taita-Taveta"},
            {"id": "ke_07", "name": "Garissa"},
            {"id": "ke_08", "name": "Wajir"},
            {"id": "ke_09", "name": "Mandera"},
            {"id": "ke_10", "name": "Marsabit"},
            {"id": "ke_11", "name": "Isiolo"},
            {"id": "ke_12", "name": "Meru"},
            {"id": "ke_13", "name": "Tharaka-Nithi"},
            {"id": "ke_14", "name": "Embu"},
            {"id": "ke_15", "name": "Kitui"},
            {"id": "ke_16", "name": "Machakos"},
            {"id": "ke_17", "name": "Makueni"},
            {"id": "ke_18", "name": "Nyandarua"},
            {"id": "ke_19", "name": "Nyeri"},
            {"id": "ke_20", "name": "Kirinyaga"},
            {"id": "ke_21", "name": "Murang'a"},
            {"id": "ke_22", "name": "Kiambu"},
            {"id": "ke_23", "name": "Turkana"},
            {"id": "ke_24", "name": "West Pokot"},
            {"id": "ke_25", "name": "Samburu"},
            {"id": "ke_26", "name": "Trans Nzoia"},
            {"id": "ke_27", "name": "Uasin Gishu"},
            {"id": "ke_28", "name": "Elgeyo-Marakwet"},
            {"id": "ke_29", "name": "Nandi"},
            {"id": "ke_30", "name": "Baringo"},
            {"id": "ke_31", "name": "Laikipia"},
            {"id": "ke_32", "name": "Nakuru"},
            {"id": "ke_33", "name": "Narok"},
            {"id": "ke_34", "name": "Kajiado"},
            {"id": "ke_35", "name": "Kericho"},
            {"id": "ke_36", "name": "Bomet"},
            {"id": "ke_37", "name": "Kakamega"},
            {"id": "ke_38", "name": "Vihiga"},
            {"id": "ke_39", "name": "Bungoma"},
            {"id": "ke_40", "name": "Busia"},
            {"id": "ke_41", "name": "Siaya"},
            {"id": "ke_42", "name": "Kisumu"},
            {"id": "ke_43", "name": "Homa Bay"},
            {"id": "ke_44", "name": "Migori"},
            {"id": "ke_45", "name": "Kisii"},
            {"id": "ke_46", "name": "Nyamira"},
            {"id": "ke_47", "name": "Nairobi City"}
        ]
        return {"status": True, "data": counties}

    def get_lgas(self, state_id):
        if not state_id:
            return {"status": False, "message": "State ID required", "data": []}
            
        lgas = [
            {"id": f"{state_id}_sub1", "name": f"Sub-county 1 (Central)"},
            {"id": f"{state_id}_sub2", "name": f"Sub-county 2 (North)"},
            {"id": f"{state_id}_sub3", "name": f"Sub-county 3 (South)"},
            {"id": f"{state_id}_sub4", "name": f"Sub-county 4 (East)"},
            {"id": f"{state_id}_sub5", "name": f"Sub-county 5 (West)"},
        ]
        
        # If Nairobi (ke_47) provide real sub-counties
        if state_id == "ke_47":
            lgas = [
                {"id": "ke_47_01", "name": "Westlands"},
                {"id": "ke_47_02", "name": "Dagoretti North"},
                {"id": "ke_47_03", "name": "Dagoretti South"},
                {"id": "ke_47_04", "name": "Langata"},
                {"id": "ke_47_05", "name": "Kibra"},
                {"id": "ke_47_06", "name": "Roysambu"},
                {"id": "ke_47_07", "name": "Kasarani"},
                {"id": "ke_47_08", "name": "Ruaraka"},
                {"id": "ke_47_09", "name": "Embakasi South"},
                {"id": "ke_47_10", "name": "Embakasi North"},
                {"id": "ke_47_11", "name": "Embakasi Central"},
                {"id": "ke_47_12", "name": "Embakasi East"},
                {"id": "ke_47_13", "name": "Embakasi West"},
                {"id": "ke_47_14", "name": "Makadara"},
                {"id": "ke_47_15", "name": "Kamukunji"},
                {"id": "ke_47_16", "name": "Starehe"},
                {"id": "ke_47_17", "name": "Mathare"}
            ]
            
        return {"status": True, "data": lgas}
