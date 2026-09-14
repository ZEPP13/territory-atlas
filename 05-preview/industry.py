#!/usr/bin/env python3
"""Industry families, industry profiles and the flow-application library.

Two jobs:

1. Fold the 45 free-text sectors that came out of five different source systems into
   a small set of **industry families** that a person can hold in their head and that
   a map marker can carry as one icon. The original sector string is never discarded —
   it survives as the subindustry, so nothing is lost by grouping.

2. State, per family, what that industry actually does with fluid: which flow
   applications are typical, which measurement technology suits each one, what plant
   scale means *in that industry*, and what to ask on a first visit.

Everything here is an industry-level assumption, applied by rule. It is deliberately
separate from anything a source verified about a specific plant — see potential.py,
which keeps the two apart when it scores.
"""

# --------------------------------------------------------------------- families
# order == legend order == categorical colour slot order (see palette.py)
FAMILIES = [
    ("data-center",  "Data centers",                        "server"),
    ("chemicals",    "Chemicals",                           "molecule"),
    ("food-bev",     "Food & beverage",                     "wheat"),
    ("pharma",       "Pharmaceuticals & biotech",           "capsule"),
    ("power",        "Power generation",                    "bolt"),
    ("paper-wood",   "Pulp, paper & wood",                  "tree"),
    ("metals",       "Metals, minerals & building materials","ingot"),
    ("oil-gas",      "Oil, gas, terminals & fuels",         "tank"),
    ("marine",       "Marine & shipbuilding",               "ship"),
    ("federal",      "Federal & defense",                   "shield"),
    ("campus",       "Campuses, healthcare & district energy","building"),
    ("other-mfg",    "Other manufacturing & industrial",    "factory"),
    ("water",        "Water & wastewater treatment",        "droplet"),
]
FAMILY_ORDER = [f[0] for f in FAMILIES]

# every sector string present in the merged data -> family
SECTOR_TO_FAMILY = {
    "data-center": "data-center",

    "chemical": "chemicals", "chemical-specialty": "chemicals",
    "chemical-commodity": "chemicals", "chemical-distribution": "chemicals",
    "plastics-rubber": "chemicals",

    "food-beverage": "food-bev", "brewing-distilling": "food-bev", "tobacco": "food-bev",

    "pharmaceutical": "pharma",

    "power-generation": "power", "solar-storage": "power",
    # waste-services holds solvent recyclers and a water treatment plant, not generation
    "waste-services": "other-mfg",

    "pulp-paper": "paper-wood", "pulp-paper-converting": "paper-wood",
    "wood-products": "paper-wood",

    "metals-minerals": "metals", "primary-metals": "metals", "fabricated-metals": "metals",
    "aggregates-mining": "metals", "building-materials": "metals",

    "refining-terminals": "oil-gas", "terminals-custody": "oil-gas",
    "midstream-gas": "oil-gas", "renewable-fuels": "oil-gas", "gas-distribution": "oil-gas",

    "naval-shipyard": "marine", "transportation-oem": "marine",

    "federal-defense": "federal", "aerospace-defense-oem": "federal",
    "federal-research": "federal",

    "higher-ed-campus": "campus", "healthcare-campus": "campus", "district-energy": "campus",

    "other-industrial": "other-mfg", "industrial-manufacturing": "other-mfg",
    "machinery-oem": "other-mfg", "semiconductor": "other-mfg", "electronics": "other-mfg",
    "textiles": "other-mfg", "advanced-manufacturing": "other-mfg",
    "logistics": "other-mfg", "distribution": "other-mfg",

    "municipal-water": "water", "municipal-wastewater": "water",
    "industrial-water-treatment": "water",
}

# Sub-sectors that carry almost no process fluid. Kept, never deleted, but flagged so
# they can be reviewed as a block rather than silently inflating the territory count.
LOW_FLOW_SECTORS = {"logistics", "distribution", "solar-storage", "aggregates-mining"}

# --------------------------------------------------------- flow-application library
# tech codes: CO coriolis · MG magnetic · VX vortex · CU clamp-on ultrasonic
APPS = {
 "chilled_water":  ("Chilled-water supply and return, BTU/energy metering",
                    "Large-diameter water, often no shutdown window available", ["CU", "MG"]),
 "cond_water":     ("Condenser and cooling-tower circulating water",
                    "Very large diameter; inline meters are cost-prohibitive", ["CU", "MG"]),
 "ct_makeup":      ("Cooling-tower make-up and blowdown, cycles-of-concentration control",
                    "Conductive water, moderate line size", ["MG", "CU"]),
 "steam_header":   ("Plant steam header and distribution to units",
                    "Saturated or superheated steam, no moving parts wanted", ["VX"]),
 "cond_return":    ("Condensate return and recovery",
                    "Flashing two-phase service; a returns balance nobody has", ["VX", "CO"]),
 "bfw":            ("Boiler feedwater and economiser flow",
                    "High pressure, accuracy drives efficiency", ["CO", "VX"]),
 "fuel_gas":       ("Fuel gas to boilers, dryers and burners",
                    "Natural gas at the burner front, billing-adjacent", ["VX", "CU"]),
 "plant_air":      ("Compressed air and nitrogen headers",
                    "Leak and load surveys; where the energy money hides", ["VX", "CU"]),
 "process_liquid": ("Process liquid transfer between unit operations",
                    "Core production measurement", ["CO", "MG"]),
 "corrosive":      ("Acid, caustic and other corrosive or toxic service",
                    "No wetted parts and no leak path is the requirement", ["CU", "CO"]),
 "slurry":         ("Slurry, stock and solids-bearing streams",
                    "Abrasive and conductive; obstructions are not an option", ["MG"]),
 "hygienic":       ("Hygienic and sanitary product transfer, CIP return",
                    "3-A / BPE, mass rather than volume, cleanability", ["CO", "MG"]),
 "clean_util":     ("Clean utilities — WFI, purified water, clean steam",
                    "Non-conductive high-purity water; validation burden on any breach", ["CO", "CU", "VX"]),
 "dosing":         ("Chemical dosing and additive injection",
                    "Small lines, ratio control, sometimes non-conductive", ["CO", "MG"]),
 "custody":        ("Custody transfer and truck/rail/marine loading",
                    "The measurement someone gets an invoice from", ["CO"]),
 "tank_transfer":  ("Tank-to-tank and terminal line transfers",
                    "Inventory reconciliation and loss control", ["CO", "CU"]),
 "hydrocarbon":    ("Hydrocarbon and non-conductive liquid lines",
                    "A magmeter cannot go here", ["CO", "CU", "VX"]),
 "cryogenic":      ("Cryogenic and industrial-gas service",
                    "Cannot breach the line; extreme temperature", ["CU", "CO"]),
 "effluent":       ("Effluent, pretreatment and permitted discharge",
                    "Permit-reportable; the number goes to the regulator", ["MG", "CU"]),
 "raw_water":      ("Raw and service water intake",
                    "Large diameter, often buried or hard to access", ["CU", "MG"]),
 "wash_water":     ("Wash-down, process water and sanitation water",
                    "Volume-heavy, conductive", ["MG"]),
 "district":       ("District heating/cooling distribution to buildings",
                    "Campus loop energy balance, building-level sub-metering", ["CU", "VX"]),
 "quench":         ("Quench, scrubber and gas-cleaning water",
                    "Dirty water, environmental-control duty", ["MG", "CU"]),
 "shipboard":      ("Shipboard and dockside systems under test",
                    "Systems that cannot be cut into, ever", ["CU"]),
 "base_util":      ("Base and installation utility distribution",
                    "Steam, chilled water and water mains across a campus", ["CU", "VX", "MG"]),
 "lube_coolant":   ("Coolant, lubricant and hydraulic circuits",
                    "Small, non-conductive, machine-level", ["CO", "VX"]),
 "muni_process":   ("Treatment-process and distribution flow",
                    "Municipal duty — outside the flow portfolio boundary", ["MG", "CU"]),
}

# ----------------------------------------------------------------------- profiles
# intensity 0-3 : how much measurable fluid this industry moves per site, by nature
# breadth   0-3 : how many *distinct* measurement duties a typical site carries
# scale     : which plant-scale signal actually means something in this industry,
#             with bands appropriate to THIS industry, not borrowed from another
PROFILES = {
 "chemicals": dict(
   intensity=3, breadth=3, scale=("employees", 50, 250),
   scale_note="Chemical plants run continuously with modest headcount; 250 staff is a large site.",
   why="Continuous liquid and vapour processing. Measurement density per unit operation is the "
       "highest of any industry in the territory, and much of the service is corrosive, toxic or "
       "non-conductive.",
   apps=["process_liquid", "corrosive", "steam_header", "cond_return", "ct_makeup",
         "dosing", "effluent", "plant_air", "hydrocarbon", "bfw"],
   ask=["Which lines have no measurement today because installing one meant a shutdown?",
        "What is the turnaround cycle, and when does instrument replacement get budgeted?",
        "Which DCS or control platform, and who owns the instrument standard?",
        "Where does the plant mass balance currently not close?"]),

 "pharma": dict(
   intensity=3, breadth=3, scale=("employees", 100, 500),
   scale_note="Pharma sites are staff-heavy relative to fluid volume; headcount tracks the number "
              "of suites and utility systems, not throughput.",
   why="Clean utilities, hygienic product transfer and tight documentation. Breaching a validated "
       "pressure boundary is a paperwork event, which changes which technologies are viable.",
   apps=["clean_util", "hygienic", "process_liquid", "chilled_water", "steam_header",
         "dosing", "plant_air", "ct_makeup", "effluent"],
   ask=["Which utilities are validated, and what does re-validation cost if a line is cut?",
        "WFI and clean-steam loop metering — measured, or assumed?",
        "Is this commercial manufacturing, clinical/CDMO, or R&D scale?",
        "Who owns the utilities versus the process instruments?"]),

 "food-bev": dict(
   intensity=3, breadth=3, scale=("employees", 75, 300),
   scale_note="Food and beverage plants are labour-intensive; headcount is a fair proxy for the "
              "number of processing and packaging lines.",
   why="Hygienic product transfer, heavy water and CIP duty, steam for cook and sterilise, and "
       "refrigeration. Product measurement is usually mass, not volume.",
   apps=["hygienic", "wash_water", "steam_header", "cond_return", "process_liquid",
         "ct_makeup", "dosing", "effluent", "chilled_water"],
   ask=["Is product measured by mass or by volume, and does that match how it is sold?",
        "How much water per unit of product, and is it metered by line?",
        "CIP chemical and water use — measured per circuit?",
        "Is there an on-site pretreatment plant before the municipal discharge?"]),

 "paper-wood": dict(
   intensity=3, breadth=3, scale=("employees", 80, 350),
   scale_note="Mills carry large headcount; a 350-plus site is an integrated mill rather than a "
              "converting or sawmill operation.",
   why="Stock and white-water systems move enormous volumes of abrasive, conductive slurry, and "
       "integrated mills run their own steam and power.",
   apps=["slurry", "steam_header", "cond_return", "bfw", "cond_water", "raw_water",
         "effluent", "dosing", "quench", "fuel_gas"],
   ask=["Consistency and stock flow control — what is installed and how old?",
        "Is there a recovery boiler or on-site generation, and is the steam balance metered?",
        "Where is the mill's water balance weakest?",
        "Integrated mill, or converting only?"]),

 "power": dict(
   intensity=3, breadth=2, scale=("mw", 25, 250),
   scale_note="Generating capacity is the only scale figure that means anything here; staffing is "
              "small and unrelated to output. Solar and storage carry no process fluid at all.",
   why="Circulating water, feedwater and condensate at very large line sizes, plus thermal "
       "performance testing that needs measurement where no permanent meter exists.",
   apps=["cond_water", "bfw", "cond_return", "steam_header", "fuel_gas", "raw_water",
         "ct_makeup", "quench", "effluent"],
   ask=["Is thermal performance tested, and with what?",
        "Circulating-water flow — measured, or inferred from pump curves?",
        "What is the outage schedule, and what gets replaced during it?",
        "Is this plant dispatched, or effectively idle?"]),

 "oil-gas": dict(
   intensity=3, breadth=2, scale=("employees", 12, 50),
   scale_note="Terminals and pipeline facilities run with very few staff regardless of throughput — "
              "headcount is a weak signal here and scale should be read from the subindustry and "
              "from registry evidence instead.",
   why="Custody transfer is the highest-value measurement in the portfolio, and almost everything "
       "in the line is non-conductive, which rules a magmeter out.",
   apps=["custody", "tank_transfer", "hydrocarbon", "process_liquid", "fuel_gas",
         "dosing", "effluent", "cryogenic"],
   ask=["Where does custody actually change hands, and what measures it?",
        "How is the meter proved, and how often?",
        "What is the current loss-and-gain reconciliation showing?",
        "Truck, rail, marine or pipeline receipt — which, and at what rate?"]),

 "data-center": dict(
   intensity=2.5, breadth=2, scale=("sqft", 80000, 300000),
   scale_note="Floor area (or IT load) is the scale signal. Headcount is meaningless — a very "
              "large hall may carry fewer than fifty staff.",
   why="Chilled-water and condenser loops at large diameter, running continuously with no shutdown "
       "window, and an operator under real pressure to prove energy efficiency per rack.",
   apps=["chilled_water", "cond_water", "ct_makeup", "raw_water", "plant_air", "fuel_gas"],
   ask=["Is cooling energy metered per hall or per loop, or estimated from design?",
        "Air-cooled, water-cooled or moving to liquid cooling?",
        "What is the WUE/PUE reporting obligation, and where does the number come from?",
        "Is there a shutdown window on the chilled-water loop? (Usually not — that is the point.)"]),

 "marine": dict(
   intensity=2, breadth=3, scale=("employees", 150, 1000),
   scale_note="Shipyards are among the largest employers in the territory; headcount genuinely "
              "tracks yard size and the number of systems under test.",
   why="Shipboard and dockside systems are tested and commissioned without being cut into, and the "
       "yard itself runs a full industrial utility plant.",
   apps=["shipboard", "steam_header", "cond_water", "plant_air", "raw_water",
         "process_liquid", "effluent", "chilled_water"],
   ask=["How are shipboard systems flow-tested during commissioning today?",
        "Which government contract vehicle covers instrument purchases?",
        "Is the yard's own utility plant metered, or allocated?",
        "What are the badging, escort and clearance requirements?"]),

 "federal": dict(
   intensity=2, breadth=2, scale=("employees", 200, 1500),
   scale_note="Installation headcount is a rough proxy for the size of the utility plant, not for "
              "process throughput; many federal sites report no usable scale figure at all.",
   why="Installation utility systems — steam, chilled water and distribution mains — plus test and "
       "research loops. Procurement path, not process, is usually the gate.",
   apps=["base_util", "steam_header", "chilled_water", "raw_water", "district",
         "fuel_gas", "plant_air", "effluent"],
   ask=["Who holds the base operations and maintenance contract?",
        "Which vehicle — NAVFAC, GSA, SEWP, DLA — and which prime do we sell through?",
        "Is utility distribution metered per building, or allocated by floor area?",
        "What clearance and site-access process applies?"]),

 "campus": dict(
   intensity=2, breadth=2, scale=("employees", 400, 2500),
   scale_note="For a hospital or university the staff count stands in for the size of the central "
              "plant and the number of buildings on the loop.",
   why="Central utility plants run campus steam and chilled water year-round, and building-level "
       "sub-metering is usually incomplete.",
   apps=["district", "chilled_water", "steam_header", "cond_return", "ct_makeup",
         "bfw", "raw_water", "plant_air"],
   ask=["Is building-level energy sub-metered, or allocated by square footage?",
        "Is there a campus energy or decarbonisation commitment with a reporting obligation?",
        "Who runs the central plant — in-house, or an energy services contractor?",
        "Where does the campus loop balance fail to close?"]),

 "metals": dict(
   intensity=2, breadth=2, scale=("employees", 60, 300),
   scale_note="Headcount tracks the number of lines and furnaces reasonably well in metals and "
              "building materials.",
   why="Furnace cooling, quench, scrubber water and process gas. Steady utility duty rather than "
       "the dense process measurement of a chemical plant.",
   apps=["cond_water", "quench", "ct_makeup", "fuel_gas", "plant_air", "slurry",
         "raw_water", "effluent", "lube_coolant"],
   ask=["Furnace and caster cooling water — metered per circuit?",
        "Scrubber and gas-cleaning water duty?",
        "Where does the energy audit say the losses are?",
        "Is there a permitted discharge with a reported flow number?"]),

 "other-mfg": dict(
   intensity=1, breadth=1, scale=("employees", 75, 400),
   scale_note="A broad category. Headcount and floor area are used together because neither alone "
              "says much across such a mixed group.",
   why="Mixed light manufacturing. Flow content is usually utility-side — compressed air, cooling "
       "water, process heating — rather than product measurement.",
   apps=["plant_air", "ct_makeup", "steam_header", "process_liquid", "wash_water",
         "lube_coolant", "chilled_water", "effluent"],
   ask=["What does this plant actually make, and does any liquid move in a pipe?",
        "Compressed-air system size — and has anyone ever surveyed it for leaks?",
        "Is there process heating or cooling with a water loop?",
        "Is this a manufacturing site at all, or a warehouse?"]),

 "water": dict(
   intensity=3, breadth=2, scale=("employees", 15, 60),
   scale_note="Municipal plants report small headcount regardless of plant capacity; treated "
              "volume is the real scale figure and is not in this data set.",
   why="Large-diameter treatment and distribution flow. Real measurement duty, but municipal water "
       "and wastewater utilities sit outside this portfolio and are hidden by default.",
   apps=["muni_process", "raw_water", "effluent", "dosing", "slurry"],
   ask=["Industrial pretreatment inside a plant is in scope — is any of this that?",
        "Who specifies the meter: the utility, or its design engineer?"]),
}

# Generation is not one industry for flow purposes. A nuclear or biomass plant runs a full
# water/steam cycle; a peaking turbine burns gas a few hundred hours a year; a landfill-gas
# engine set meters gas and little else. Scored separately (added 2026-09-13).
POWER_SUBTYPES = {
 "steam": dict(intensity=3, breadth=3, label="Steam-cycle plant",
   why="Nuclear, coal, biomass, waste-to-energy and cogeneration plants run a full water and steam "
       "cycle: circulating water, feedwater, condensate and makeup. The densest flow work in generation."),
 "thermal": dict(intensity=3, breadth=2, label="Thermal plant",
   why="A fuel-burning generating plant with large water and fuel systems; whether it runs a steam "
       "cycle is not established from the data."),
 "hydro": dict(intensity=2, breadth=1, label="Hydroelectric plant", max_band="Medium",
   why="Turbine water flow at very large scale, normally measured by the dam operator's own methods; "
       "limited instrument work beyond cooling and auxiliary systems."),
 "peaker": dict(intensity=1.5, breadth=1, label="Peaking plant", max_band="Medium",
   why="Simple-cycle turbines that run only at peak demand. With no steam cycle the flow work is mainly "
       "fuel gas and injection water, used a small fraction of the year."),
 "landfill_gas": dict(intensity=1, breadth=1, label="Landfill-gas engines", max_band="Low",
   why="Small engine sets burning landfill gas. Flow work is gas metering and little else."),
 "small_unit": dict(intensity=1, breadth=1, label="Small generating unit", max_band="Low",
   why="No generating capacity was matched from EPA eGRID and the plant reports five or fewer staff: most "
       "likely a small distributed or backup unit, or a second listing of a plant recorded elsewhere."),
}

TECH = {
 "CO": ("Coriolis", "Micro Motion", "Direct mass, high accuracy, handles non-conductive fluid."),
 "MG": ("Magnetic",  "Rosemount",   "Conductive liquids and slurries; no obstruction in the line."),
 "VX": ("Vortex",    "Rosemount",   "Steam, gas and condensate; no moving parts."),
 "CU": ("Clamp-on ultrasonic", "Flexim",
        "Nothing enters the pipe: no cut, no shutdown, no leak path, and it works on large "
        "diameters and non-conductive fluids."),
}

def family_of(sector):
    return SECTOR_TO_FAMILY.get(sector, "other-mfg")

def profile_of(family):
    return PROFILES.get(family, PROFILES["other-mfg"])
