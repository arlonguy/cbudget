package carbon.budget

# By default, don’t allow unless the rule matches
default allow = false

# Allow when the predicted emission rate is within the threshold rate
allow {
  input.predicted_emission_rate_gph <= input.budget_threshold_rate_gph
}