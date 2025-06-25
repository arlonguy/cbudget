package carbon

default allow = false

# Single‐line Pass/Fail boolean rule
allow = true if input.emission_rate_gph <= input.threshold_rate_gph
