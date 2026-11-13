n = floor(29.99*288000);
x = randn(n,1);
k = 20;
m = max(x); tic; for j=1:k, m = max(x); end; t1 = toc/k*1000;
[m,ix] = max(x); tic; for j=1:k, [m,ix] = max(x); end; t2 = toc/k*1000;
printf("octave max(x)        : %.2f ms\n", t1);
printf("octave [x,ix]=max(x) : %.2f ms\n", t2);
