package carbon

default allow = false

# Single‐line boolean rule using the new `if` syntax
allow = true if input.emission_rate_gph <= input.threshold_rate_gph
