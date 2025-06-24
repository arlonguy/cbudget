package carbon

default allow = false

allow {
  input.emission_rate_gph <= input.threshold_rate_gph
}
