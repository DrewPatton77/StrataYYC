-- Maps each service group as it appears in the data to a stable reporting group and a readable name.
-- The City renames and merges service groups over time (for example CBS became DBBS in 2024), so a trend by
-- raw service_group shows false collapses. Charts should use reporting_group_name instead.
-- Groups that are not listed here keep their own name (see dim_service).
-- Evidence for the merges: the renamed groups contain the same service names, for example
-- "CBS Inspection - Electrical" and "DBBS Inspection - Electrical". Readable names describe what the group's
-- services are, taken from the service names, not from an official list.

SELECT *
FROM (
    VALUES
        ('Roads',                      'Roads',                      'Roads'),
        ('WRS',                        'WRS',                        'Waste & Recycling'),
        ('Bylaw',                      'Bylaw',                      'Bylaw'),
        ('Parks',                      'Parks',                      'Parks'),
        ('WATS',                       'WATS',                       'Water & Sewer'),
        ('WATR',                       'WATR',                       'Water Regulation & Inspection'),
        ('AS',                         'AS',                         'Animal Services'),
        ('CT',                         'CT',                         'Transit'),
        ('CT AC',                      'CT AC',                      'Transit Trip Feedback'),
        ('CFD',                        'CFD',                        'Fire Department'),
        ('Corporate',                  'Corporate',                  'Corporate'),
        ('Recreation',                 'Recreation',                 'Recreation'),
        ('Compliance',                 'Compliance',                 'Compliance'),
        ('Law',                        'Law',                        'Law'),
        ('Opinions on Business Units', 'Opinions on Business Units', 'Opinions on Business Units'),
        ('311',                        '311',                        '311 Service'),
        ('311 Contact Us',             '311',                        '311 Service'),
        -- renamed or merged groups
        ('CBS Inspection',             'DBBS Inspection',            'Building Inspections'),
        ('DBBS Inspection',            'DBBS Inspection',            'Building Inspections'),
        ('CBS',                        'DBBS',                       'Development & Building Services'),
        ('DBBS',                       'DBBS',                       'Development & Building Services'),
        ('Finance',                    'AT',                         'Assessment & Tax'),
        ('AT',                         'AT',                         'Assessment & Tax'),
        ('CN',                         'RSP',                        'Social Programs & Seniors'),
        ('RSP',                        'RSP',                        'Social Programs & Seniors')
) AS t (service_group, reporting_group, reporting_group_name)