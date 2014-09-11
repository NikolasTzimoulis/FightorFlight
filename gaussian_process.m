function [f_new, s2_new, loglikelihood] = gaussian_process(X, t, kernel, s2, x_new)

N = size(X,1);
K = zeros(N);
k_new = zeros(N,1);
for i = 1:N
    for j = 1:N
        K(i,j) = kernel(X(i,:), X(j,:));
    end
    k_new(i) = kernel(X(i,:), x_new);
end
        
L = chol(K+s2*eye(length(K)), 'lower');
a = L'\(L\t);
f_new = k_new'*a;
v = L\k_new;
s2_new = kernel(x_new, x_new) - v'*v;
loglikelihood = -0.5*t'*a-sum(log(diag(L)))-(N/2)*log(2*pi);

end

