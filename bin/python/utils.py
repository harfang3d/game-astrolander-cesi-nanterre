
def clamp(val, low1, high1):
	return min(max(val, low1), high1)

def range_adjust(val, low1, high1, low2, high2):
	return low2 + (val - low1) * (high2 - low2) / (high1 - low1)