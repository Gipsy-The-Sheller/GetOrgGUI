#include "matcher.h"
#include <vector>  // 添加 vector 头文件
#include <algorithm>  // 添加 algorithm 头文件用于 min_element

Matcher::Matcher() {
}

Matcher::~Matcher() {
}

bool Matcher::matchWithOneInsertion(const char* insData, const char* normalData, int cmplen, int diffLimit) {
    // 使用 vector 替代变长数组
    std::vector<int> accMismatchFromLeft(cmplen);
    std::vector<int> accMismatchFromRight(cmplen);

    // accMismatchFromLeft[0]: head vs. head
    // accMismatchFromRight[cmplen-1]: tail vs. tail
    accMismatchFromLeft[0] = insData[0] == normalData[0] ? 0 : 1;
    accMismatchFromRight[cmplen - 1] = insData[cmplen] == normalData[cmplen - 1] ? 0 : 1;

    for (int i = 1; i < cmplen; i++) {
        if (insData[i] != normalData[i])
            accMismatchFromLeft[i] = accMismatchFromLeft[i - 1] + 1;
        else
            accMismatchFromLeft[i] = accMismatchFromLeft[i - 1];

        if (accMismatchFromLeft[i] + accMismatchFromRight[cmplen - 1] > diffLimit)
            break;
    }

    for (int i = cmplen - 2; i >= 0; i--) {
        if (insData[i + 1] != normalData[i])
            accMismatchFromRight[i] = accMismatchFromRight[i + 1] + 1;
        else
            accMismatchFromRight[i] = accMismatchFromRight[i + 1];

        if (accMismatchFromRight[i] + accMismatchFromLeft[0] > diffLimit) {
            for (int p = 0; p < i; p++)
                accMismatchFromRight[p] = diffLimit + 1;
            break;
        }
    }

    // insertion can be from pos = 1 to cmplen - 1
    for (int i = 1; i < cmplen; i++) {
        if (accMismatchFromLeft[i - 1] + accMismatchFromRight[cmplen - 1] > diffLimit)
            return false;
        int diff = accMismatchFromLeft[i - 1] + accMismatchFromRight[i];
        if (diff <= diffLimit)
            return true;
    }

    return false;
}

int Matcher::diffWithOneInsertion(const char* insData, const char* normalData, int cmplen, int diffLimit) {
    // 使用 vector 替代变长数组
    std::vector<int> accMismatchFromLeft(cmplen);
    std::vector<int> accMismatchFromRight(cmplen);

    // accMismatchFromLeft[0]: head vs. head
    // accMismatchFromRight[cmplen-1]: tail vs. tail
    accMismatchFromLeft[0] = insData[0] == normalData[0] ? 0 : 1;
    accMismatchFromRight[cmplen - 1] = insData[cmplen] == normalData[cmplen - 1] ? 0 : 1;

    for (int i = 1; i < cmplen; i++) {
        if (insData[i] != normalData[i])
            accMismatchFromLeft[i] = accMismatchFromLeft[i - 1] + 1;
        else
            accMismatchFromLeft[i] = accMismatchFromLeft[i - 1];

        if (accMismatchFromLeft[i] + accMismatchFromRight[cmplen - 1] > diffLimit)
            break;
    }

    for (int i = cmplen - 2; i >= 0; i--) {
        if (insData[i + 1] != normalData[i])
            accMismatchFromRight[i] = accMismatchFromRight[i + 1] + 1;
        else
            accMismatchFromRight[i] = accMismatchFromRight[i + 1];

        if (accMismatchFromRight[i] + accMismatchFromLeft[0] > diffLimit) {
            for (int p = 0; p < i; p++)
                accMismatchFromRight[p] = diffLimit + 1;
            break;
        }
    }

    int minDiff = 100000000;
    // insertion can be from pos = 1 to cmplen - 1
    for (int i = 1; i < cmplen; i++) {
        if (accMismatchFromLeft[i - 1] + accMismatchFromRight[cmplen - 1] > diffLimit)
            return -1; // -1 means higher than diffLimit
        int diff = accMismatchFromLeft[i - 1] + accMismatchFromRight[i];
        if (diff < minDiff)
            minDiff = diff;
    }

    return minDiff;
}