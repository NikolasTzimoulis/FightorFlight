close all;
clear; clc;
load analytics.txt;
fights = [(1:length(analytics))' analytics(:,2)];
predictedFuture = length(analytics)/50;
modelDensity = 50;

runs=1;
mse = zeros(runs,1);
s2 = 1;
for run=1:runs
    trainPercent = 100;
    isTrain = crossvalind('Kfold', length(fights), 100) <= trainPercent;
    train_X = fights(find(isTrain),1);
    train_t = fights(find(isTrain),2);
    test_X = fights(find(isTrain==0),1);
    test_t = fights(find(isTrain==0),2);

    %figure;
    plot(train_X, train_t, 'Color', [0.5,0.5,0.5], 'Marker', 's', 'MarkerFaceColor', 'k', 'LineStyle', ':');hold on;

    test_out = zeros(length(test_X),1);
    i=1;
    for x_new = test_X'
        [f_new, s2_new, loglikelihood] = gaussian_process(train_X, train_t, @squared_exponential, s2, x_new);
        test_out(i) = f_new;
        mse(run)  = mse(run) + ((test_out(i)-test_t(i))^2)/length(test_X);
        i = i+1;
    end

    plot(test_X, test_out', 'rs', 'MarkerFaceColor',[1 0 0], 'MarkerSize',7)
    plot(test_X, test_t', 'gs', 'MarkerFaceColor',[0 1 0], 'MarkerSize',7)

    t_curve = 1:(length(fights)+predictedFuture)/modelDensity:length(fights)+predictedFuture;
    i=1;
    for x_new = t_curve
        [f_new, s2_new, loglikelihood] = gaussian_process(train_X, train_t, @squared_exponential, s2, x_new);
        f_curve(i) = f_new;
        evar(i) = s2_new;
        i = i+1;
    end

    errorbar(t_curve, f_curve, evar.*f_curve, 'c-'); %hold off;
    axis([1 max(t_curve) -1 30]);
end

mean(mse)
saveas(gcf, 'analytics.png')