function k = squared_exponential( x1, x2 )

theta = 10e2; 
lambda = 10e2; 
k = theta * exp(-(1/(2*lambda))*(x1-x2)'*(x1-x2));

end

