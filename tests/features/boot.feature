Feature: Wake Sarah up.

Scenario: Default setting
    When No extra configuration file is given
    Then Default configuration is applied

Scenario: Invalid setting
    When Provided configuration file path is invalid
    Then Raise exception
