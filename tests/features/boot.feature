Feature: Wake Sarah up.

    Scenario: Invalid setting
        When Provided configuration file path is invalid
        Then Raise exception
