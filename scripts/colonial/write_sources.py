"""Write data/processed/sources_colonial.csv and check every source_id used is listed.
Run: python3 -I scripts/colonial/write_sources.py
"""
import csv
from pathlib import Path

ROOT = Path("/home/user/migration")
P = ROOT / "data/processed"
ACC = "2026-10-18"

S = [
    ("hsus1975_Z1_19",
     "U.S. Bureau of the Census, Historical Statistics of the United States, Colonial Times to 1970 (Bicentennial ed., 1975), Part 2, Ch. Z, Series Z 1-19 'Estimated Population of American Colonies: 1610 to 1780' (compiled by Stella H. Sutherland), p. 1168",
     "https://www2.census.gov/library/publications/1975/compendia/hist_stats_colonial-1970/hist_stats_colonial-1970p2-chZ.pdf",
     "Scanned image PDF (raw: data/raw/hsus_1975_chZ/chZ.pdf, Z 1-19 on PDF page 16). Totals machine-read from the Wikipedia reproduction and verified against the HSUS Total row; Negro panel transcribed from the scan and verified by column sums. Same chapter: Z 155-164 Charleston imports by origin 1706-1775 used as a cross-check only."),
    ("wikipedia_list_colonial_population",
     "Wikipedia, 'List of colonial and pre-Federal U.S. historical population' (wikitext), reproducing HSUS Z 1-19 totals",
     "https://en.wikipedia.org/w/index.php?title=List_of_colonial_and_pre-Federal_U.S._historical_population&action=raw",
     "Used only as a machine-readable copy of HSUS Z 1-19 totals; one cell corrected to HSUS (New Hampshire 1700 = 4,958, not 4,658); its Total row has typos for 1630/1640/1650/1700."),
    ("census_twps0056_appA",
     "Campbell Gibson and Kay Jung, 'Historical Census Statistics on Population Totals by Race, 1790 to 1990, and by Hispanic Origin, 1970 to 1990, for the United States, Regions, Divisions, and States', U.S. Census Bureau Population Division Working Paper No. 56 (2002), Appendix A tables A-21 to A-26 (1840-1790)",
     "https://www2.census.gov/library/working-papers/2002/demo/pop-twps0056/appendixA.xlsx",
     "Landing page https://www.census.gov/library/working-papers/2002/demo/POP-twps0056.html. State rows are for CURRENT state boundaries (e.g., Virginia excludes West Virginia; Maine shown separately before 1820). 'As published' rows (old Virginia, Northwest Territory, etc.) not used."),
    ("slavevoyages_tast_estimates",
     "SlaveVoyages, Trans-Atlantic Slave Trade - Estimates (assessment database), disembarked captives by year, embarkation region and disembarkation region; queried via the site's public API endpoint /api/assessment/crosstabs/",
     "https://www.slavevoyages.org/voyage/trans-atlantic (Estimates); API https://www.slavevoyages.org/api/assessment/crosstabs/",
     "Raw JSON responses with request payloads in data/raw/slavevoyages/api/est_*.json; script scripts/colonial/fetch_slavevoyages.py. Mainland North America total 388,744."),
    ("slavevoyages_iastd",
     "SlaveVoyages, Intra-American Slave Trade Database (voyage-level, dataset=1), imputed captives disembarked by year of arrival, region of purchase and principal region of disembarkation; via /api/voyage/crosstabs/",
     "https://www.slavevoyages.org/voyage/intra-american ; API https://www.slavevoyages.org/api/voyage/crosstabs/",
     "Documented voyages only (lower bound). Includes coastwise/domestic US trade (purchase region in Mainland North America). Canada excluded; 54 captives with unknown arrival year skipped. Raw: data/raw/slavevoyages/api/ia_*.json"),
    ("fogleman1992_jih_via_tomlins2001",
     "Aaron S. Fogleman, 'Migrations to the Thirteen British North American Colonies, 1700-1775: New Estimates', Journal of Interdisciplinary History 22:4 (1992), 691-709; decade x group table as reproduced in Christopher Tomlins, 'Reconsidering Indentured Servitude: European Migration and the Early American Labor Force, 1600-1775', Labor History 42:1 (2001), Appendix III Table A1",
     "https://library.fes.de/libalt/journals/swetsfulltext/11116561.pdf",
     "Primary JIH article is paywalled (JSTOR); numbers taken from Tomlins' reproduction (thousands, one decimal). Grand total 307.4k Europeans; with Fogleman's 278,400 Africans = 585,800."),
    ("tomlins2001_laborhistory",
     "Christopher Tomlins, 'Reconsidering Indentured Servitude: European Migration and the Early American Labor Force, 1600-1775', Labor History 42:1 (2001), 5-43, text and Appendix I/III",
     "https://library.fes.de/libalt/journals/swetsfulltext/11116561.pdf",
     "17th-c. regional synthesis (Chesapeake 108,000; New England 24,000; Delaware Valley 15,000; Lower South 8,000; New Netherland 6,000) and literature ranges for 18th-c. groups. Raw: data/raw/tomlins_2001_laborhistory/"),
    ("tomlins2001_table1_menard",
     "Tomlins (2001) Table 1 'European migration, servant migration and population estimates, Maryland and Virginia, 1600-1700', derived from Russell R. Menard, 'British Migration to the Chesapeake Colonies in the Seventeenth Century', in Carr et al., Colonial Chesapeake Society (1988), Tables 2-3, and McCusker & Menard, The Economy of British America (1985), Table 6.4",
     "https://library.fes.de/libalt/journals/swetsfulltext/11116561.pdf",
     "Decades ending 1610-1630 are approximations; for 1681-1700 only servant migrants are given (all-migrant counts derived at Tomlins' 80% servant assumption)."),
    ("tomlins2001_table6",
     "Tomlins (2001) Table 6 'Immigration to the Delaware Valley, 1680-1780' (British: Fischer, Albion's Seed, and Bailyn, Voyagers to the West; German and Irish: Fogleman 1992 pp. 702, 705; Philadelphia arrivals: Klepp 1989)",
     "https://library.fes.de/libalt/journals/swetsfulltext/11116561.pdf",
     "Regional detail (Delaware Valley ports). 1770s printed total 15,902 vs column sum 15,932."),
    ("gemery_via_tomlins2001",
     "Henry A. Gemery, 'Emigration from the British Isles to the New World, 1630-1700: Inferences from Colonial Populations', Research in Economic History 5 (1980), and 'Markets for Migrants' (1986), p. 40; as reported in Tomlins (2001)",
     "https://library.fes.de/libalt/journals/swetsfulltext/11116561.pdf", "Secondary report of Gemery's 155,000 (39,000 north / 116,000 south)."),
    ("menard_via_tomlins2001",
     "Russell R. Menard, 'British Migration to the Chesapeake Colonies in the Seventeenth Century' (1988), best guess and range, as reported in Tomlins (2001) Appendix I; James Horn, Adapting to a New World (1994), p. 25",
     "https://library.fes.de/libalt/journals/swetsfulltext/11116561.pdf", ""),
    ("horn_virtualjamestown",
     "James Horn, 'Leaving England: The Social Background of Indentured Servants in the Seventeenth Century', Virtual Jamestown essay (Colonial Williamsburg Foundation / Virginia Center for Digital History)",
     "http://www.virtualjamestown.org/essays/horn_essay.html",
     "17th-c. English emigration by destination and Chesapeake decadal ranges."),
    ("fogleman1998_jah_table1_via_umbc",
     "Aaron S. Fogleman, 'From Slaves, Convicts, and Servants to Free Passengers: The Transformation of Immigration in the Era of the American Revolution', Journal of American History 85:1 (1998), 43-76, Table 1 'Estimated Immigration into the Thirteen Colonies and the United States ... 1607-1819', as reproduced in UMBC Center for History Education teaching handout 'Resource Sheet #07'",
     "https://www2.umbc.edu/che/tahlessons/pdf/historylabs/What_Factors_Br_student:RS07.pdf",
     "Handout reproduces only the 1607-1699 and 1700-1775 rows (by status). 1700-1775 sums to 585,800 incl. 278,400 slaves (also quoted by germanna_note0406). Rows 1776-1809/1810-1819 of Table 1 not obtained."),
    ("germanna_note0406",
     "John Blankenbaker, Germanna History Notes, Note 406 (quoting Fogleman, Hopeful Journeys, 1996)",
     "https://germanna.org/wp-content/uploads/history/note0406.html",
     "Cross-check only: African 278,400; German 84,500; N. Irish 66,100; S. Irish 42,500; Scots 35,300; English 44,100; Welsh 29,000; Other 5,900 (blog misstates the sum as 585,000; figures sum to 585,800)."),
    ("fogleman1998_via_nowrasteh2026",
     "Alex Nowrasteh, '1776 America had a higher immigrant share than today' (Substack, 2026), quoting Fogleman (1998): 973,600 slave and free entrants 1700-1809; 198,400 in 1607-1699 incl. 33,200 slaves",
     "https://www.alexnowrasteh.com/p/1776-america-had-a-higher-immigrant",
     "Advocacy-leaning secondary source; used only to derive Fogleman's 1776-1809 total by subtraction (alt row)."),
    ("earlyamericancrime_vaver",
     "Anthony Vaver, 'Convict Voyages: Overview', Early American Crime (earlyamericancrime.com), citing Ekirch, Bound for America (1987) and Fogleman (1998)",
     "https://www.earlyamericancrime.com/convict-transportation/convict-voyages/overview-2",
     "Convicts 1718-1775: >16,000 from Ireland; ~34,000 English; ~50,000 total."),
    ("ekirch_via_tomlins2001",
     "A. Roger Ekirch, Bound for America: The Transportation of British Convicts to the Colonies, 1718-1775 (1987), 114-16, as reported in Tomlins (2001)",
     "https://library.fes.de/libalt/journals/swetsfulltext/11116561.pdf", ""),
    ("meyerink_szucs1997_via_wikipedia",
     "Kory L. Meyerink and Loretto Dennis Szucs, The Source: A Guidebook of American Genealogy (Ancestry, 1997), 'immigrants before 1790' by country, as tabulated in Wikipedia 'Demographic history of the United States'",
     "https://en.wikipedia.org/w/index.php?title=Demographic_history_of_the_United_States&action=raw",
     "Not verified against the book (archive.org copy is lending-only). Used as alt estimates, mainly for small origin groups (Dutch, French, Jews, Swedes)."),
    ("cohn_ehnet_grabbe",
     "Raymond L. Cohn, 'Immigration to the United States', EH.Net Encyclopedia (ed. R. Whaples), Table 1 (average yearly totals 1630-1700, 1700-1780, 1780-1819; 'Years before 1820: Grabbe (1989)'); same figures in Engerman & Margo, 'Free Labor and Slave Labor', in Irwin & Sylla (eds.), Founding Choices (NBER/Chicago 2010), Table 9.5, citing Cohn, Mass Migration under Sail (2009)",
     "https://eh.net/encyclopedia/immigration-to-the-united-states/ ; https://www.nber.org/system/files/chapters/c11745/c11745.pdf",
     "Period totals in the CSV are DERIVED (average x years). Underlying: H.-J. Grabbe, 'European Immigration to the United States in the Early National Period, 1783-1820', Proc. American Philosophical Society 133:2 (1989), 190-214 (paywalled; not obtained)."),
    ("hsus1949_chB_note",
     "U.S. Bureau of the Census, Historical Statistics of the United States, 1789-1945 (1949), Chapter B, general note to series B 304-352 (citing Treasury Bureau of Statistics, Monthly Summary of Commerce and Finance, No. 12, 1902-03, p. 4336)",
     "https://www2.census.gov/library/publications/1949/compendia/hist_stats_1789-1945/hist_stats_1789-1945-chB.pdf",
     "250,000 immigrants 1783-1820; attributed to William J. Bromwell (1856) by immigrantentrepreneurship_vol2."),
    ("immigrantentrepreneurship_vol2",
     "William J. Hausman, 'Volume 2 Introduction: The Emergence of an Industrial Nation, 1840-1893', Immigrant Entrepreneurship (German Historical Institute)",
     "https://www.immigrantentrepreneurship.org/entries/volume-2-introduction/", "Attribution of the 250,000 figure to Bromwell (1856)."),
    ("boyd_immigrantentrepreneurship",
     "James Boyd, 'Merchants of Migration: Keeping the German Atlantic Connected in America's Early National Period', Immigrant Entrepreneurship (German Historical Institute), citing H.-J. Grabbe, Vor der grossen Flut (2001) and F. Grubb, German Immigration and Servitude in America (2011)",
     "https://www.immigrantentrepreneurship.org/entries/merchants-of-migration-keeping-the-german-atlantic-connected-in-americas-early-national-period/",
     "German-speaking arrivals 1800-1808 and 1815-1820."),
    ("wikipedia_new_sweden", "Wikipedia, 'New Sweden' (wikitext)",
     "https://en.wikipedia.org/w/index.php?title=New_Sweden&action=raw", "'roughly 600 Swedes and Finns'; weak underlying citation."),
    ("wikipedia_jews_colonial", "Wikipedia, 'History of the Jews in Colonial America' (wikitext)",
     "https://en.wikipedia.org/w/index.php?title=History_of_the_Jews_in_Colonial_America&action=raw", "23 Jewish refugees to New Amsterdam, 1654."),
    ("wikipedia_huguenots", "Wikipedia, 'Huguenots' (wikitext), section on North America",
     "https://en.wikipedia.org/w/index.php?title=Huguenots&action=raw", "Manakin Town 1700: 390 original settlers."),
    ("wikipedia_islenos", "Wikipedia, 'Isleños' (wikitext)",
     "https://en.wikipedia.org/w/index.php?title=Isle%C3%B1os&action=raw", "2,100 Canary Islanders to Spanish Louisiana 1778-1783; family counts for Texas (1731) and Florida (1757-59)."),
    ("wikipedia_louisiana_acadians", "Wikipedia, 'Louisiana (New France)' and 'Acadians' (wikitext)",
     "https://en.wikipedia.org/w/index.php?title=Louisiana_(New_France)&action=raw ; https://en.wikipedia.org/w/index.php?title=Acadians&action=raw",
     "Acadians to Louisiana (~3,000-4,000; 1,633 from France in 1785); 1717 colony population 550."),
]


def main():
    with (P / "sources_colonial.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "citation", "url", "accessed", "notes"])
        for sid, cit, url, notes in S:
            w.writerow([sid, cit, url, ACC, notes])
    ids = {s[0] for s in S}
    used = set()
    for fn in ["flows_colonial_by_origin.csv", "slave_trade_arrivals.csv", "population_1610_1840.csv"]:
        for r in csv.DictReader((P / fn).open()):
            used.add(r["source_id"])
    missing = used - ids
    assert not missing, missing
    print("sources:", len(S), "used:", len(used), "unused (context/cross-check):", sorted(ids - used))


if __name__ == "__main__":
    main()
