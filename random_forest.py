#!/usr/bin/env python

import numpy as np
import pandas as pd
import pdb
import asyncio
import random

np.random.seed(42)


class Tree:
    def __init__(self, index, max_depth, min_size, depth=1):
        self.depth, self.max_depth, self.min_size = depth, max_depth, min_size
        self.index = index

    def fit(self, data):
        depth, max_depth, min_size = self.depth, self.max_depth, self.min_size
        index = self.index
        # print(self.index, self.depth)
        # child nodes
        self.child = dict()
        # category if the current node is a leaf node
        self.category = None
        # get categories
        self.categories = self.__get_categories(data)
        # a tuple: (row, column), representing the point where
        # we split the data into the left/right node
        self.split_point = self.__get_best_split_point(data) 
        groups = self.__split(data, *self.split_point)
        for i, group in enumerate(groups):
            if len(group) < min_size or depth >= max_depth:
                self.category = self.most_common_category(data)
            else:
                self.child[i] = child = Tree(index, max_depth, min_size, depth+1)
                child.fit(group)
        return 1

    async def fit_async(self, data):
        depth, max_depth, min_size = self.depth, self.max_depth, self.min_size
        index = self.index
        # print(self.index, self.depth)
        # child nodes
        self.child = dict()
        # category if the current node is a leaf node
        self.category = None
        # get categories
        self.categories = self.__get_categories(data)
        # a tuple: (row, column), representing the point where
        # we split the data into the left/right node
        self.split_point = self.__get_best_split_point(data) 
        groups = self.__split(data, *self.split_point)
        jobs = []
        for i, group in enumerate(groups):
            if len(group) < min_size or depth >= max_depth:
                self.category = self.most_common_category(data)
            else:
                self.child[i] = child = Tree(index, max_depth, min_size, depth+1)
                jobs.append(child.fit(group))
        await asyncio.gather(*jobs)
        return 1

    def __get_categories(self, data):
        return set(row[-1] for row in data)

    def __get_features(self, data):
        n_all_features = len(data[0]) - 1
        n_features = int(np.sqrt(n_all_features))
        return np.random.choice(n_all_features, n_features, replace=False)

    def __get_best_split_point(self, data):
        # print(len(data))
        features = self.__get_features(data)
        x, y, sv, gini_index = None, None, None, None
        for index in range(len(data)):
            # pdb.set_trace()
            for feature in features:
                split_value = data[index][feature]
                groups = self.__split(data, index, feature, split_value)
                current_gini_index = self.__get_gini_index(data, groups)
                if gini_index is None or current_gini_index < gini_index:
                    x, y, sv = index, feature, split_value
                    gini_index = current_gini_index
        return x, y, data[x][y]

    def __split(self, data, x, y, split_value):
        left, right = [], []
        for i, row in enumerate(data):
            if row[y] > split_value:
                right.append(row)
            else:
                left.append(row)
        return left, right

    def __get_gini_index(self, data, groups):
        categories = self.categories
        gini_index = 0
        for group in groups:
            n_group = len(group)
            if n_group == 0:
                continue
            score = 0
            data_list = [row[-1] for row in data]
            for category in categories:
                p = data_list.count(category) / n_group
                score += p * p
            gini_index += (1 - score) * n_group / len(data)
        return gini_index

    def most_common_category(self, data):
        categories = [row[-1] for row in data]
        return max(set(categories), key=categories.count)

    def predict(self, row):
        if self.category is not None:
            return self.category
        i, j, split_value = self.split_point
        if row[j] <= split_value:
            child = self.child[0]
        else:
            child = self.child[1]
        return child.predict(row)


class RandomForest:
    def __init__(self, n_trees, max_depth, min_size, n_sample_rate):
        self.n_sample_rate = n_sample_rate
        self.trees = [Tree(index, max_depth, min_size) for index in range(n_trees)]

    def sample_data(self, data):
        n_sample = int(len(data) * self.n_sample_rate)
        return random.sample(data, n_sample)

    def fit(self, data):
        _ = [tree.fit(self.sample_data(data)) for tree in self.trees]

    async def fit_async(self, data):
        await asyncio.gather(*[tree.fit_async(self.sample_data(data)) for tree in self.trees])

    def predict(self, row):
        prediction = [tree.predict(row) for tree in self.trees]
        return max(set(prediction), key=prediction.count)

    def accuracy(self, validate_data):
        n_correct = 0
        categories = [(self.predict(row[:-1]), row[-1]) for row in validate_data]
        for pred_category, true_category in categories:
            if pred_category == true_category:
                n_correct += 1
        return n_correct / len(validate_data)


class CrossValidationSplitter:
    def __init__(self, all_data, k_fold, rate):
        self.all_data, self.k_fold, self.rate = all_data, k_fold, rate
        self.n_iteration = 0
        self.__do_train_test_split()

    def __iter__(self):
        return self

    def __next__(self):
        if self.n_iteration >= self.k_fold:
            raise StopIteration
        self.n_iteration += 1
        return self.__get_train_validate_split()

    def __get_train_validate_split(self):
        data = self.train_validate_data[:]
        random.shuffle(data)
        train_data = data[self.n_train_validate_split:]
        validate_data = data[:self.n_train_validate_split]
        return train_data, validate_data

    def __do_train_test_split(self):
        rate, all_data = self.rate, self.all_data
        np.random.shuffle(all_data)
        perm = np.random.permutation(len(all_data))
        n_train_test_split = int(len(all_data) * rate)
        self.train_validate_data = all_data[: n_train_test_split]
        self.test_data = all_data[n_train_test_split:]
        self.n_train_validate_split = len(
            self.train_validate_data)//self.k_fold


if __name__ == "__main__":
    data = pd.read_csv('resources/sonar.all-data.csv',
            header=None).values.tolist()
    for n_tree in [1,4,16]:
        accuracies = []
        model = None
        splitter = CrossValidationSplitter(data, k_fold=5, rate=0.9)
        for train_data, validate_data in splitter:
            #pdb.set_trace()
            print(len(data), len(train_data), len(validate_data))
            model = RandomForest(
                n_trees=n_tree,
                max_depth=5,
                min_size=1,
                n_sample_rate=0.9
            )
            #asyncio.run(model.fit(train_data))
            model.fit(train_data)
            accuracies.append(model.accuracy(validate_data))
        validation_accuracy = np.mean(accuracies)
        test_accuracy = model.accuracy(splitter.test_data)
        print(
            f"Mean cross validation accuracy for {n_tree} trees: {validation_accuracy}")
        print(f"Test accuracy for {n_tree} trees: {test_accuracy}")
