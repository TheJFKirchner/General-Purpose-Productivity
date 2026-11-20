"""Input files loaded as they are: one write_source line per file (table name = what sections and reports call it).
as_of_from names the file's date column, so the header's "Data as of" follows the data. Refresh: replace the files
(same names), then npm run pipeline."""
from _dataset_io import write_source

# write_source("claims", "../inputs/claims.csv", as_of_from="service_month")
